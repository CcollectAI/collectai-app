import { track, identifyUser, resetAnalytics, trackScreen, initAnalytics } from '../track';
import type { AnalyticsEvent } from '../track';

// Mock posthog-react-native
const mockCapture = jest.fn();
const mockIdentify = jest.fn();
const mockReset = jest.fn();
const mockScreen = jest.fn();

jest.mock('posthog-react-native', () => ({
  PostHog: jest.fn().mockImplementation(() => ({
    capture: mockCapture,
    identify: mockIdentify,
    reset: mockReset,
    screen: mockScreen,
  })),
}));

beforeEach(() => {
  jest.clearAllMocks();
});

describe('analytics/track', () => {
  describe('before initialization', () => {
    it('track() is a no-op', () => {
      // PostHog not initialized — should not throw
      track({ name: 'user_logged_in', properties: { method: 'email' } });
      expect(mockCapture).not.toHaveBeenCalled();
    });

    it('identifyUser() is a no-op', () => {
      identifyUser('user-123');
      expect(mockIdentify).not.toHaveBeenCalled();
    });

    it('resetAnalytics() is a no-op', () => {
      resetAnalytics();
      expect(mockReset).not.toHaveBeenCalled();
    });

    it('trackScreen() is a no-op', () => {
      trackScreen('/home');
      expect(mockScreen).not.toHaveBeenCalled();
    });
  });

  describe('initAnalytics', () => {
    it('skips init when API key is undefined', () => {
      initAnalytics(undefined);
      track({ name: 'quickscan_started' });
      expect(mockCapture).not.toHaveBeenCalled();
    });

    it('skips init when API key is empty string', () => {
      initAnalytics('');
      track({ name: 'quickscan_started' });
      expect(mockCapture).not.toHaveBeenCalled();
    });

    it('initializes PostHog with a valid API key', () => {
      initAnalytics('phc_test_key_123');
      // After init, calls should go through
      track({ name: 'quickscan_started' });
      expect(mockCapture).toHaveBeenCalledWith('quickscan_started', undefined);
    });
  });

  describe('after initialization', () => {
    beforeAll(() => {
      initAnalytics('phc_test_key');
    });

    it('track() forwards event name and properties', () => {
      const event: AnalyticsEvent = {
        name: 'item_added',
        properties: { source: 'manual', category: 'pokemon' },
      };
      track(event);
      expect(mockCapture).toHaveBeenCalledWith('item_added', {
        source: 'manual',
        category: 'pokemon',
      });
    });

    it('track() handles events without properties', () => {
      track({ name: 'quickscan_started' });
      expect(mockCapture).toHaveBeenCalledWith('quickscan_started', undefined);
    });

    it('identifyUser() forwards user ID and traits', () => {
      identifyUser('user-456', { plan: 'pro', region: 'eu' });
      expect(mockIdentify).toHaveBeenCalledWith('user-456', { plan: 'pro', region: 'eu' });
    });

    it('resetAnalytics() calls posthog.reset()', () => {
      resetAnalytics();
      expect(mockReset).toHaveBeenCalledTimes(1);
    });

    it('trackScreen() forwards screen name', () => {
      trackScreen('/(tabs)/portfolio');
      expect(mockScreen).toHaveBeenCalledWith('/(tabs)/portfolio', undefined);
    });
  });
});
