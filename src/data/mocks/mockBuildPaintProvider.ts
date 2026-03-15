/**
 * Mock build & paint domain provider + analytics metrics.
 */

import type {
  AnalyticsMetrics,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
  CreateBuildPaintProjectInput,
} from '../types';
import { MOCK_TWITCH_CREATORS } from '../../mockData';
import { logger } from '@/lib/logger';
import {
  mockBuildPaintProjects,
  mockBuildPaintSteps,
  mockBuildPaintNotes,
} from './mockState';

export async function getAnalyticsMetrics(): Promise<AnalyticsMetrics> {
  const projects = Array.from(mockBuildPaintProjects.values());
  const activeProjects = projects.filter((p) => p.status === 'active').length;
  const backlogProjects = projects.filter((p) => p.status === 'backlog').length;
  const completedProjects = projects.filter((p) => p.isCompleted).length;
  const totalBuildMinutes = 1260;
  const totalBuildHours = totalBuildMinutes / 60;

  const twitchCreatorsTracked = MOCK_TWITCH_CREATORS.length;
  const twitchCreatorsLive = MOCK_TWITCH_CREATORS.filter((c) => c.liveNow).length;

  return {
    activeProjects,
    backlogProjects,
    completedProjects,
    totalBuildMinutes,
    totalBuildHours,
    twitchCreatorsTracked,
    twitchCreatorsLive,
  };
}

export async function listBuildPaintProjects(): Promise<BuildPaintProject[]> {
  return Array.from(mockBuildPaintProjects.values()).sort((a, b) =>
    b.updatedAt.localeCompare(a.updatedAt)
  );
}

export async function createBuildPaintProject(input: CreateBuildPaintProjectInput): Promise<BuildPaintProject> {
  const id = `bp-mock-${Date.now()}`;
  const now = new Date().toISOString();
  const project: BuildPaintProject = {
    id,
    title: input.title,
    category: input.category || null,
    categoryId: input.categoryId || null,
    itemId: input.itemId || null,
    status: 'backlog',
    percent: 0,
    isCompleted: false,
    notes: null,
    createdAt: now,
    updatedAt: now,
  };
  mockBuildPaintProjects.set(id, project);
  mockBuildPaintSteps.set(id, []);
  mockBuildPaintNotes.set(id, []);
  logger.info('[MockDataProvider] createBuildPaintProject', { id, title: input.title });
  return project;
}

export async function setBuildPaintProgress(projectId: string, percent: number, status?: string): Promise<void> {
  const project = mockBuildPaintProjects.get(projectId);
  if (!project) return;

  project.percent = Math.max(0, Math.min(100, percent));
  if (status) project.status = status;
  project.updatedAt = new Date().toISOString();
  mockBuildPaintProjects.set(projectId, project);
  logger.info('[MockDataProvider] setBuildPaintProgress', { projectId, percent, status });
}

export async function markBuildPaintProjectComplete(projectId: string, isCompleted: boolean): Promise<void> {
  const project = mockBuildPaintProjects.get(projectId);
  if (!project) return;

  project.isCompleted = isCompleted;
  project.status = isCompleted ? 'completed' : 'active';
  if (isCompleted) project.percent = 100;
  project.updatedAt = new Date().toISOString();
  mockBuildPaintProjects.set(projectId, project);
  logger.info('[MockDataProvider] markBuildPaintProjectComplete', { projectId, isCompleted });
}

export async function listBuildPaintSteps(projectId: string): Promise<BuildPaintStep[]> {
  const steps = mockBuildPaintSteps.get(projectId) || [];
  return [...steps].sort((a, b) => a.sortOrder - b.sortOrder);
}

export async function addBuildPaintStep(projectId: string, title: string): Promise<BuildPaintStep> {
  const steps = mockBuildPaintSteps.get(projectId) || [];
  const sortOrder = steps.length > 0 ? Math.max(...steps.map((s) => s.sortOrder)) + 1 : 1;
  const step: BuildPaintStep = {
    id: `step-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
    projectId,
    title,
    isDone: false,
    sortOrder,
    createdAt: new Date().toISOString(),
  };
  steps.push(step);
  mockBuildPaintSteps.set(projectId, steps);
  const project = mockBuildPaintProjects.get(projectId);
  if (project) {
    project.updatedAt = new Date().toISOString();
    mockBuildPaintProjects.set(projectId, project);
  }
  logger.info('[MockDataProvider] addBuildPaintStep', { projectId, title, stepId: step.id });
  return step;
}

export async function toggleBuildPaintStep(stepId: string, isDone: boolean): Promise<void> {
  const entries = Array.from(mockBuildPaintSteps.entries());
  for (let i = 0; i < entries.length; i++) {
    const [projectId, steps] = entries[i];
    const step = steps.find((s) => s.id === stepId);
    if (step) {
      step.isDone = isDone;
      const project = mockBuildPaintProjects.get(projectId);
      if (project) {
        project.updatedAt = new Date().toISOString();
        mockBuildPaintProjects.set(projectId, project);
      }
      logger.info('[MockDataProvider] toggleBuildPaintStep', { stepId, isDone });
      return;
    }
  }
}

export async function listBuildPaintNotes(projectId: string): Promise<BuildPaintNote[]> {
  const notes = mockBuildPaintNotes.get(projectId) || [];
  return [...notes].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function addBuildPaintNote(projectId: string, body: string): Promise<BuildPaintNote> {
  const notes = mockBuildPaintNotes.get(projectId) || [];
  const note: BuildPaintNote = {
    id: `note-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
    projectId,
    body,
    createdAt: new Date().toISOString(),
  };
  notes.push(note);
  mockBuildPaintNotes.set(projectId, notes);
  const project = mockBuildPaintProjects.get(projectId);
  if (project) {
    project.updatedAt = new Date().toISOString();
    mockBuildPaintProjects.set(projectId, project);
  }
  logger.info('[MockDataProvider] addBuildPaintNote', { projectId, noteId: note.id });
  return note;
}

export async function listBuildPaintProjectsByCategory(categoryId: string): Promise<BuildPaintProject[]> {
  const all = await listBuildPaintProjects();
  return all.filter((p) => p.categoryId === categoryId);
}

export async function listBuildPaintProjectsByItem(itemId: string): Promise<BuildPaintProject[]> {
  const all = await listBuildPaintProjects();
  return all.filter((p) => p.itemId === itemId);
}

export async function applyStepTemplate(projectId: string, categoryId: string): Promise<BuildPaintStep[]> {
  const { getStepTemplateForCategory } = await import('../../constants/buildStepTemplates');
  const template = getStepTemplateForCategory(categoryId);
  const steps: BuildPaintStep[] = [];
  for (const s of template.steps) {
    const step = await addBuildPaintStep(projectId, s.label);
    steps.push(step);
  }
  return steps;
}

export async function updateBuildPaintProject(projectId: string, patch: { paintRecipes?: unknown[] }): Promise<void> {
  const project = mockBuildPaintProjects.get(projectId);
  if (project && patch.paintRecipes !== undefined) {
    (project as Record<string, unknown>).paintRecipes = patch.paintRecipes;
  }
}
