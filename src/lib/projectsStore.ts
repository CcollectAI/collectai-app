export type ProjectStep = {
  id: string;
  label: string;
  done: boolean;
};

export type CollectorProject = {
  id: string;
  title: string;
  categoryId?: string;
  status: "ongoing" | "closed";
  steps: ProjectStep[];
  notes: string;
  createdAt: number;
  updatedAt: number;
};

const STORAGE_KEY = "collectors.projects.v1";

// In-memory fallback (works even if AsyncStorage isn't installed)
let mem: CollectorProject[] | null = null;

function now() {
  return Date.now();
}

function seeded(): CollectorProject[] {
  const baseSteps = [
    { id: "plan", label: "Plan / reference", done: true },
    { id: "prime", label: "Prime", done: false },
    { id: "base", label: "Basecoat", done: false },
    { id: "shade", label: "Wash / shade", done: false },
    { id: "highlight", label: "Highlights", done: false },
    { id: "detail", label: "Details", done: false },
    { id: "base2", label: "Basing", done: false },
    { id: "varnish", label: "Varnish", done: false },
    { id: "photo", label: "Photos", done: false },
  ];

  return [
    {
      id: "proj-ironclad",
      title: "Ironclad Dreadnought (Display)",
      categoryId: "warhammer",
      status: "ongoing",
      steps: baseSteps.map((s) => ({ ...s })),
      notes: "Target: crisp edge highlights. Track paint mixes + varnish choice.",
      createdAt: now() - 1000 * 60 * 60 * 24 * 3,
      updatedAt: now() - 1000 * 60 * 60 * 2,
    },
    {
      id: "proj-charizard",
      title: "Charizard PSA prep (Binder → Submission)",
      categoryId: "pokemon",
      status: "closed",
      steps: [
        { id: "select", label: "Select candidates", done: true },
        { id: "sleeve", label: "Sleeve / semi-rigid", done: true },
        { id: "scan", label: "Scan condition / centering", done: true },
        { id: "submit", label: "Submit", done: true },
      ],
      notes: "Closed: submitted batch #4.",
      createdAt: now() - 1000 * 60 * 60 * 24 * 18,
      updatedAt: now() - 1000 * 60 * 60 * 24 * 5,
    },
  ];
}

async function tryAsyncStorage():
  Promise<{ getItem(k: string): Promise<string | null>; setItem(k: string, v: string): Promise<void> } | null> {
  try {
    // optional dependency
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require("@react-native-async-storage/async-storage");
    const AsyncStorage = mod?.default ?? mod;
    if (!AsyncStorage?.getItem || !AsyncStorage?.setItem) return null;
    return AsyncStorage;
  } catch {
    return null;
  }
}

export function projectCompletionPct(p: CollectorProject): number {
  const total = p.steps?.length ?? 0;
  if (!total) return 0;
  const done = p.steps.filter((s) => s.done).length;
  return Math.round((done / total) * 100);
}

export async function loadProjects(): Promise<CollectorProject[]> {
  if (mem) return mem;

  const AS = await tryAsyncStorage();
  if (AS) {
    const raw = await AS.getItem(STORAGE_KEY);
    if (raw) {
      try {
        mem = JSON.parse(raw);
        return mem!;
      } catch {
        // fallthrough to seed
      }
    }
    mem = seeded();
    await AS.setItem(STORAGE_KEY, JSON.stringify(mem));
    return mem;
  }

  mem = seeded();
  return mem;
}

export async function saveProjects(next: CollectorProject[]): Promise<void> {
  mem = next;
  const AS = await tryAsyncStorage();
  if (AS) await AS.setItem(STORAGE_KEY, JSON.stringify(next));
}

export async function getProjectById(id: string): Promise<CollectorProject | undefined> {
  const all = await loadProjects();
  return all.find((p) => p.id === id);
}

export async function upsertProject(p: CollectorProject): Promise<void> {
  const all = await loadProjects();
  const idx = all.findIndex((x) => x.id === p.id);
  const next = [...all];
  if (idx >= 0) next[idx] = { ...p, updatedAt: now() };
  else next.unshift({ ...p, createdAt: now(), updatedAt: now() });
  await saveProjects(next);
}

export async function setProjectStatus(id: string, status: "ongoing" | "closed"): Promise<void> {
  const all = await loadProjects();
  const next = all.map((p) => (p.id === id ? { ...p, status, updatedAt: now() } : p));
  await saveProjects(next);
}
