import { useSyncExternalStore } from 'react';

export type ProjectStatus =
  | 'backlog'
  | 'in-progress'
  | 'paused'
  | 'completed';

export type ProjectUpdate = {
  id: string;
  projectId: string;
  createdAt: string; // ISO string
  note?: string;
  photoUri?: string;
  timeSpentMinutes?: number | null;
};

export type Project = {
  id: string;
  userId: string | null;
  itemId?: string | null;
  title: string;
  category?: string | null;
  status: ProjectStatus;
  percentComplete: number; // 0–100
  notes?: string | null;
  createdAt: string; // ISO
  updatedAt: string; // ISO
};

export type ProjectsState = {
  projects: Record<string, Project>;
  updates: Record<string, ProjectUpdate[]>;
};

type Listener = () => void;

const listeners = new Set<Listener>();

// For now, we use a demo seed. Later we can hydrate from backend / storage.
let state: ProjectsState = {
  projects: {},
  updates: {},
};

function seedDemoIfEmpty() {
  if (Object.keys(state.projects).length > 0) return;

  const now = new Date();
  const toIso = (d: Date) => d.toISOString();

  const p1Id = 'demo-project-1';
  const p2Id = 'demo-project-2';

  const created1 = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const created2 = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);

  const updates1: ProjectUpdate[] = [
    {
      id: 'demo-update-1-1',
      projectId: p1Id,
      createdAt: toIso(created1),
      note: 'Unboxed kit, dry fit main parts.',
      timeSpentMinutes: 60,
    },
    {
      id: 'demo-update-1-2',
      projectId: p1Id,
      createdAt: toIso(
        new Date(created1.getTime() + 2 * 24 * 60 * 60 * 1000),
      ),
      note: 'Primed and base-coated armor pieces.',
      timeSpentMinutes: 90,
    },
  ];

  const updates2: ProjectUpdate[] = [
    {
      id: 'demo-update-2-1',
      projectId: p2Id,
      createdAt: toIso(created2),
      note: 'Built main frame, started detailing.',
      timeSpentMinutes: 75,
    },
  ];

  const project1: Project = {
    id: p1Id,
    userId: 'demo-user',
    itemId: null,
    title: 'Warhammer squad – Urban camo scheme',
    category: 'warhammer',
    status: 'in-progress',
    percentComplete: 40,
    notes: 'Going for a muted urban palette with some neon accents.',
    createdAt: toIso(created1),
    updatedAt: toIso(
      new Date(created1.getTime() + 3 * 24 * 60 * 60 * 1000),
    ),
  };

  const project2: Project = {
    id: p2Id,
    userId: 'demo-user',
    itemId: null,
    title: 'HG Gundam – panel lining & decals',
    category: 'gunpla',
    status: 'backlog',
    percentComplete: 10,
    notes: 'Snap build done, need to panel line and apply decals.',
    createdAt: toIso(created2),
    updatedAt: toIso(created2),
  };

  state = {
    projects: {
      [project1.id]: project1,
      [project2.id]: project2,
    },
    updates: {
      [p1Id]: updates1,
      [p2Id]: updates2,
    },
  };
}

function emitChange() {
  for (const listener of listeners) {
    listener();
  }
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): ProjectsState {
  // Lazy seed so we always have at least demo content
  seedDemoIfEmpty();
  return state;
}

// --- Mutators ---

type NewProjectInput = {
  id?: string;
  userId?: string | null;
  itemId?: string | null;
  title: string;
  category?: string | null;
  notes?: string | null;
};

export function createProject(input: NewProjectInput): Project {
  const id = input.id ?? `project-${Date.now()}-${Math.random()}`;
  const nowIso = new Date().toISOString();

  const project: Project = {
    id,
    userId: input.userId ?? null,
    itemId: input.itemId ?? null,
    title: input.title.trim(),
    category: input.category ?? null,
    status: 'backlog',
    percentComplete: 0,
    notes: input.notes ?? null,
    createdAt: nowIso,
    updatedAt: nowIso,
  };

  state = {
    ...state,
    projects: {
      ...state.projects,
      [id]: project,
    },
    updates: {
      ...state.updates,
      [id]: state.updates[id] ?? [],
    },
  };
  emitChange();
  return project;
}

export function updateProject(
  id: string,
  patch: Partial<
    Pick<
      Project,
      'title' | 'status' | 'percentComplete' | 'notes' | 'category'
    >
  >,
): void {
  const existing = state.projects[id];
  if (!existing) return;

  const nowIso = new Date().toISOString();

  const next: Project = {
    ...existing,
    ...patch,
    percentComplete:
      patch.percentComplete != null
        ? Math.min(Math.max(patch.percentComplete, 0), 100)
        : existing.percentComplete,
    updatedAt: nowIso,
  };

  state = {
    ...state,
    projects: {
      ...state.projects,
      [id]: next,
    },
  };
  emitChange();
}

type NewProjectUpdateInput = {
  projectId: string;
  note?: string;
  photoUri?: string;
  timeSpentMinutes?: number | null;
};

export function addProjectUpdate(
  input: NewProjectUpdateInput,
): ProjectUpdate | null {
  const project = state.projects[input.projectId];
  if (!project) return null;

  const id = `pupd-${Date.now()}-${Math.random()}`;
  const nowIso = new Date().toISOString();

  const update: ProjectUpdate = {
    id,
    projectId: input.projectId,
    createdAt: nowIso,
    note: input.note,
    photoUri: input.photoUri,
    timeSpentMinutes: input.timeSpentMinutes ?? null,
  };

  const existing = state.updates[input.projectId] ?? [];

  state = {
    ...state,
    updates: {
      ...state.updates,
      [input.projectId]: [...existing, update],
    },
  };
  emitChange();
  return update;
}

export function clearAllProjects() {
  state = { projects: {}, updates: {} };
  seedDemoIfEmpty();
  emitChange();
}

// --- Selectors & hooks ---

export function getProjectsState(): ProjectsState {
  return getSnapshot();
}

export function getAllProjects(): Project[] {
  const snap = getSnapshot();
  return Object.values(snap.projects).sort((a, b) =>
    a.createdAt < b.createdAt ? 1 : -1,
  );
}

export function getProjectById(
  id: string,
): Project | undefined {
  const snap = getSnapshot();
  return snap.projects[id];
}

export function getProjectUpdates(
  projectId: string,
): ProjectUpdate[] {
  const snap = getSnapshot();
  const list = snap.updates[projectId] ?? [];
  return [...list].sort((a, b) =>
    a.createdAt < b.createdAt ? 1 : -1,
  );
}

export function useProjects(): {
  projects: Project[];
} {
  const snap = useSyncExternalStore(subscribe, getSnapshot);
  const projects = Object.values(snap.projects).sort((a, b) =>
    a.createdAt < b.createdAt ? 1 : -1,
  );
  return { projects };
}

export function useProject(
  id: string,
): { project: Project | undefined; updates: ProjectUpdate[] } {
  const snap = useSyncExternalStore(subscribe, getSnapshot);
  const project = snap.projects[id];
  const updates = (snap.updates[id] ?? []).slice().sort((a, b) =>
    a.createdAt < b.createdAt ? 1 : -1,
  );
  return { project, updates };
}
