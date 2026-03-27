/**
 * Snapshot tests for Build & Paint project components:
 * ProjectCard, CreateProjectModal, ProjectFilters.
 */
import React from 'react';
import { render, screen } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockColors = {
  card: '#FFFFFF',
  text: '#0F172A',
  muted: '#64748B',
  border: '#E2E8F0',
  accent: '#81D8D0',
  accentText: '#FFFFFF',
  background: '#F8FAFC',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  error: '#EF4444',
  info: '#3B82F6',
  brand: { base: '#81D8D0', dark: '#5FBFB6' },
};

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: mockColors, isDark: false }),
}));

jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return {
    AnimatedPressable: (props: any) => <Pressable {...props} />,
  };
});

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT',
    ALERT_TRIGGERED: 'ALERT_TRIGGERED',
  },
}));

jest.mock('../../src/lib/timeAgo', () => ({
  timeAgo: () => '3d ago',
}));

jest.mock('../../src/constants/time', () => ({
  MS_PER_DAY: 86400000,
}));

jest.mock('../../src/data/categories', () => ({
  CATEGORIES: [
    { id: 'lego', name: 'LEGO' },
    { id: 'warhammer', name: 'Warhammer' },
    { id: 'gunpla', name: 'Gunpla' },
  ],
  CATEGORY_VISUAL: {
    lego: { iconName: 'cube-outline' },
    warhammer: { iconName: 'shield-outline' },
  },
}));

jest.mock('../../src/constants/buildStepTemplates', () => ({
  BUILDABLE_CATEGORIES: ['lego', 'warhammer', 'gunpla'],
  getStepTemplateForCategory: () => null,
  getStatusDef: () => undefined,
  getStatusPipeline: () => [],
  isFinishedStatus: () => false,
}));

jest.mock('../../src/data', () => ({
  dataProvider: {
    listItems: jest.fn().mockResolvedValue([]),
    createBuildPaintProject: jest.fn().mockResolvedValue({}),
  },
}));

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: { hapticsEnabled: true, currency: 'EUR', isDark: false },
    updateSettings: jest.fn(),
  }),
}));

jest.mock('../../src/lib/format', () => ({
  formatPrice: (price: number, currency: string) => `${currency} ${price}`,
}));

jest.mock('../../src/utils/logger', () => ({
  default: { warn: jest.fn(), debug: jest.fn(), info: jest.fn(), error: jest.fn() },
}));

jest.mock('../../src/theme/tokens', () => ({
  radius: { xs: 6, sm: 10, md: 16, lg: 20, xl: 24 },
  spacing: { xxs: 4, xs: 6, sm: 10, md: 14, lg: 18, xl: 24 },
  text: { xs: 10, sm: 12, md: 14, lg: 16, xl: 20, '2xl': 24 },
  fontWeight: {
    medium: '500',
    semibold: '600',
    bold: '700',
    extrabold: '800',
  },
  shadow: {
    card: {
      shadowColor: '#000',
      shadowOpacity: 0.06,
      shadowRadius: 8,
      shadowOffset: { width: 0, height: 4 },
      elevation: 2,
    },
  },
  gap: { xxs: 2, xs: 4, sm: 6, md: 8, lg: 10, xl: 12 },
}));

// Import components after mocks
import { ProjectCard } from '../../src/components/projects/ProjectCard';
import { CreateProjectModal } from '../../src/components/projects/CreateProjectModal';
import { ProjectFilters } from '../../src/components/projects/ProjectFilters';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeProject(overrides: Record<string, unknown> = {}) {
  return {
    id: 'proj-1',
    title: 'Paint Warhammer Squad',
    category: 'Warhammer',
    categoryId: 'warhammer',
    status: 'active',
    percent: 45,
    isCompleted: false,
    notes: 'Priming done, base coat next',
    itemId: null,
    itemName: null,
    itemImageUrl: null,
    createdAt: '2025-06-01T12:00:00Z',
    updatedAt: '2025-06-10T14:00:00Z',
    ...overrides,
  } as any;
}

// ---------------------------------------------------------------------------
// ProjectCard
// ---------------------------------------------------------------------------

describe('ProjectCard', () => {
  it('renders with minimal props and matches snapshot', () => {
    const tree = render(
      <ProjectCard project={makeProject()} onPress={jest.fn()} />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders project title', () => {
    render(
      <ProjectCard
        project={makeProject({ title: 'Build LEGO Falcon' })}
        onPress={jest.fn()}
      />,
    );
    expect(screen.getByText('Build LEGO Falcon')).toBeTruthy();
  });

  it('renders completed status', () => {
    render(
      <ProjectCard
        project={makeProject({ isCompleted: true, percent: 100 })}
        onPress={jest.fn()}
      />,
    );
    expect(screen.getByText('Finished')).toBeTruthy();
    expect(screen.getByText('100%')).toBeTruthy();
  });

  it('renders linked item name', () => {
    render(
      <ProjectCard
        project={makeProject({ itemName: 'Kill Team Box' })}
        onPress={jest.fn()}
      />,
    );
    expect(screen.getByText('Kill Team Box')).toBeTruthy();
  });

  it('renders notes preview', () => {
    render(
      <ProjectCard
        project={makeProject({ notes: 'Waiting for primer to dry' })}
        onPress={jest.fn()}
      />,
    );
    expect(screen.getByText('Waiting for primer to dry')).toBeTruthy();
  });

  it('matches snapshot for completed project', () => {
    const tree = render(
      <ProjectCard
        project={makeProject({
          isCompleted: true,
          percent: 100,
          status: 'completed',
          title: 'Finished Gunpla',
        })}
        onPress={jest.fn()}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// CreateProjectModal
// ---------------------------------------------------------------------------

describe('CreateProjectModal', () => {
  it('renders when visible and matches snapshot', () => {
    const tree = render(
      <CreateProjectModal
        visible={true}
        onClose={jest.fn()}
        onCreated={jest.fn()}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders New Project title', () => {
    render(
      <CreateProjectModal
        visible={true}
        onClose={jest.fn()}
        onCreated={jest.fn()}
      />,
    );
    expect(screen.getByText('New Project')).toBeTruthy();
  });

  it('renders nothing meaningful when not visible', () => {
    const { toJSON } = render(
      <CreateProjectModal
        visible={false}
        onClose={jest.fn()}
        onCreated={jest.fn()}
      />,
    );
    // Modal with visible=false still renders but is hidden
    expect(toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// ProjectFilters
// ---------------------------------------------------------------------------

describe('ProjectFilters', () => {
  const defaultCounts = { all: 10, in_progress: 4, finished: 3, wishlist: 2 };

  it('renders with counts and matches snapshot', () => {
    const tree = render(
      <ProjectFilters
        selected="all"
        onSelect={jest.fn()}
        counts={defaultCounts}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders all filter labels', () => {
    render(
      <ProjectFilters
        selected="all"
        onSelect={jest.fn()}
        counts={defaultCounts}
      />,
    );
    expect(screen.getByText('All')).toBeTruthy();
    expect(screen.getByText('In Progress')).toBeTruthy();
    expect(screen.getByText('Finished')).toBeTruthy();
    expect(screen.getByText('Wishlist')).toBeTruthy();
  });

  it('renders count values', () => {
    render(
      <ProjectFilters
        selected="in_progress"
        onSelect={jest.fn()}
        counts={defaultCounts}
      />,
    );
    expect(screen.getByText('10')).toBeTruthy();
    expect(screen.getByText('4')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
  });

  it('matches snapshot with finished selected', () => {
    const tree = render(
      <ProjectFilters
        selected="finished"
        onSelect={jest.fn()}
        counts={defaultCounts}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});
