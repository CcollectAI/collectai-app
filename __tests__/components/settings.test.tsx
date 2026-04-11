/**
 * Settings component tests.
 *
 * Covers ProfileEditSection, AppearanceSection, and PrivacySettingsSection.
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
};

jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: mockColors, isDark: false }),
}));

const mockUpdateSettings = jest.fn();
jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: {
      hapticsEnabled: true,
      animationsEnabled: true,
      currency: 'EUR',
      isDark: false,
      region: 'europe',
      numberLocale: 'nl-NL',
    },
    updateSettings: mockUpdateSettings,
  }),
  REGION_DEFAULTS: {
    americas: { currency: 'USD', numberLocale: 'en-US' },
    europe: { currency: 'EUR', numberLocale: 'nl-NL' },
    japan: { currency: 'JPY', numberLocale: 'ja-JP' },
    korea: { currency: 'KRW', numberLocale: 'ko-KR' },
    oceania: { currency: 'AUD', numberLocale: 'en-AU' },
    other: { currency: 'USD', numberLocale: 'en-US' },
  },
}));

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
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

jest.mock('../../src/providers/useAuthContext', () => ({
  useAuthContext: () => ({
    user: { id: 'user-1', email: 'test@example.com' },
    profile: { username: 'TestUser' },
    signOut: jest.fn(),
  }),
}));

jest.mock('../../src/components/Toast', () => ({
  useToast: () => ({ showToast: jest.fn() }),
}));

jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: jest.fn().mockResolvedValue({ data: { session: null } }),
      getUser: jest.fn().mockResolvedValue({ data: { user: { id: 'user-1' } } }),
      updateUser: jest.fn().mockResolvedValue({ error: null }),
    },
    from: jest.fn(() => ({
      select: jest.fn(() => ({
        eq: jest.fn(() => ({
          single: jest.fn().mockResolvedValue({ data: null, error: null }),
        })),
      })),
      upsert: jest.fn().mockResolvedValue({ error: null }),
    })),
  },
}));

jest.mock('../../src/api/config', () => ({
  API_BASE: 'http://localhost:8000',
}));

jest.mock('../../src/api/collectorsApi', () => ({
  deleteAccount: jest.fn(),
  collectorsApi: {
    getInsuranceReportUrl: jest.fn(() => 'http://example.com/report'),
  },
}));

jest.mock('../../src/lib/logger', () => ({
  logger: { warn: jest.fn(), debug: jest.fn(), info: jest.fn(), error: jest.fn() },
}));

jest.mock('../../src/theme/tokens', () => ({
  radius: { md: 12, sm: 8, lg: 16, xl: 24 },
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
}));

// Now import components after mocks
import { ProfileEditSection } from '../../src/components/settings/ProfileEditSection';
import { AppearanceSection } from '../../src/components/settings/AppearanceSection';
import { PrivacySettingsSection } from '../../src/components/settings/PrivacySettingsSection';

// ---------------------------------------------------------------------------
// ProfileEditSection
// ---------------------------------------------------------------------------

describe('ProfileEditSection', () => {
  it('renders the Account section header', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('Account')).toBeTruthy();
  });

  it('renders the username', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('TestUser')).toBeTruthy();
  });

  it('renders the email', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('test@example.com')).toBeTruthy();
  });

  it('renders Edit Profile row', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('Edit Profile')).toBeTruthy();
    expect(screen.getByText('Change your username and bio')).toBeTruthy();
  });

  it('renders Change Password row', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('Change Password')).toBeTruthy();
    expect(screen.getByText('Update your account password')).toBeTruthy();
  });

  it('renders Sign Out button', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('Sign Out')).toBeTruthy();
  });

  it('renders Delete Account button', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('Delete Account')).toBeTruthy();
  });

  it('renders Subscription row', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('Manage Subscription')).toBeTruthy();
  });

  it('renders Two-Factor Auth row', () => {
    render(<ProfileEditSection />);
    expect(screen.getByText('Two-Factor Auth')).toBeTruthy();
  });

  it('has accessibility labels for interactive elements', () => {
    render(<ProfileEditSection />);
    expect(screen.getByLabelText('Edit profile')).toBeTruthy();
    expect(screen.getByLabelText('Change password')).toBeTruthy();
    expect(screen.getByLabelText('Sign out')).toBeTruthy();
    expect(screen.getByLabelText('Delete account')).toBeTruthy();
  });

  it('matches snapshot', () => {
    const tree = render(<ProfileEditSection />);
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// AppearanceSection
// ---------------------------------------------------------------------------

describe('AppearanceSection', () => {
  it('renders Region & Currency header', () => {
    render(<AppearanceSection />);
    expect(screen.getByText('Region & Currency')).toBeTruthy();
  });

  it('renders Preferences header', () => {
    render(<AppearanceSection />);
    expect(screen.getByText('Preferences')).toBeTruthy();
  });

  it('renders Region row with current region', () => {
    render(<AppearanceSection />);
    expect(screen.getByText('Region')).toBeTruthy();
    expect(screen.getByText('Europe')).toBeTruthy();
  });

  it('renders Currency row with current currency', () => {
    render(<AppearanceSection />);
    expect(screen.getByText('Currency')).toBeTruthy();
    expect(screen.getByText('EUR')).toBeTruthy();
  });

  it('renders Dark mode toggle', () => {
    render(<AppearanceSection />);
    expect(screen.getByText('Dark mode')).toBeTruthy();
    expect(screen.getByText('Switch between light and dark theme')).toBeTruthy();
  });

  it('renders Haptic feedback toggle', () => {
    render(<AppearanceSection />);
    expect(screen.getByText('Haptic feedback')).toBeTruthy();
    expect(screen.getByText('Vibration feedback for interactions')).toBeTruthy();
  });

  it('renders Animations toggle', () => {
    render(<AppearanceSection />);
    expect(screen.getByText('Animations')).toBeTruthy();
    expect(screen.getByText('Enable micro-animations throughout the app')).toBeTruthy();
  });

  it('has accessibility labels for toggles', () => {
    render(<AppearanceSection />);
    expect(screen.getByLabelText('Dark mode')).toBeTruthy();
    expect(screen.getByLabelText('Haptic feedback')).toBeTruthy();
    expect(screen.getByLabelText('Animations')).toBeTruthy();
  });

  it('has accessibility labels for pickers', () => {
    render(<AppearanceSection />);
    expect(screen.getByLabelText('Change region')).toBeTruthy();
    expect(screen.getByLabelText('Change currency')).toBeTruthy();
  });

  it('matches snapshot', () => {
    const tree = render(<AppearanceSection />);
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// PrivacySettingsSection
// ---------------------------------------------------------------------------

describe('PrivacySettingsSection', () => {
  it('renders Privacy section header', async () => {
    render(<PrivacySettingsSection />);
    expect(screen.getByText('Privacy')).toBeTruthy();
  });

  it('shows loading state initially', () => {
    render(<PrivacySettingsSection />);
    expect(screen.getByText('Loading settings...')).toBeTruthy();
  });

  it('renders privacy toggles after loading', async () => {
    render(<PrivacySettingsSection />);
    // Wait for the useEffect to resolve
    const label = await screen.findByText('Show collection value', {}, { timeout: 2000 });
    expect(label).toBeTruthy();
    expect(screen.getByText('Show item count')).toBeTruthy();
    expect(screen.getByText('Allow discovery')).toBeTruthy();
    expect(screen.getByText('Show online status')).toBeTruthy();
  });

  it('renders hint text for toggles', async () => {
    render(<PrivacySettingsSection />);
    const hint = await screen.findByText(
      'Display your total collection value on your profile',
      {},
      { timeout: 2000 },
    );
    expect(hint).toBeTruthy();
  });

  it('has accessibility labels for privacy toggles', async () => {
    render(<PrivacySettingsSection />);
    const toggle = await screen.findByLabelText('Show collection value', {}, { timeout: 2000 });
    expect(toggle).toBeTruthy();
    expect(screen.getByLabelText('Show item count')).toBeTruthy();
    expect(screen.getByLabelText('Allow discovery')).toBeTruthy();
    expect(screen.getByLabelText('Show online status')).toBeTruthy();
  });

  it('matches snapshot after loading', async () => {
    const tree = render(<PrivacySettingsSection />);
    await screen.findByText('Show collection value', {}, { timeout: 2000 });
    expect(tree.toJSON()).toMatchSnapshot();
  });
});
