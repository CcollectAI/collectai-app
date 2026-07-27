/**
 * Tests for the shared camera PermissionScreen.
 *
 * The bug these pin: iOS presents a permission dialog exactly ONCE per install.
 * After "Don't Allow", requestPermission() resolves immediately with
 * `granted: false, canAskAgain: false` and shows no dialog — so a button wired
 * only to requestPermission() is dead forever, with no route to Settings.
 * Reported as "I can't get camera permission on TestFlight".
 *
 * The `canAskAgain === false` case is the one that regressed in the field, so
 * it is asserted on behaviour (which handler fires), not just on copy.
 */

import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { Linking } from 'react-native';

jest.mock('@/motion', () => {
  const React = require('react');
  const { Pressable } = require('react-native');
  return {
    AnimatedPressable: (props: any) => React.createElement(Pressable, props),
  };
});

jest.mock('@/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: { CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT' },
}));

jest.mock('@/constants/colors', () => ({
  BRAND_COLORS: { tiffany: '#81D8D0' },
}));

jest.mock('@expo/vector-icons', () => {
  const React = require('react');
  const { View } = require('react-native');
  return { Ionicons: (props: any) => React.createElement(View, props) };
});

import { PermissionScreen } from '@/components/quickscan/PermissionScreen';

const colors = { background: '#FFF', text: '#000', muted: '#888' };

function setup(canAskAgain: boolean) {
  const onGrant = jest.fn();
  const onCancel = jest.fn();
  const utils = render(
    <PermissionScreen
      onGrant={onGrant}
      onCancel={onCancel}
      hapticsEnabled={false}
      canAskAgain={canAskAgain}
      colors={colors}
    />,
  );
  return { ...utils, onGrant, onCancel };
}

describe('PermissionScreen', () => {
  beforeEach(() => jest.clearAllMocks());

  describe('when iOS will still show the dialog (canAskAgain: true)', () => {
    it('offers to request permission', () => {
      const { getByText } = setup(true);
      expect(getByText('Grant Permission')).toBeTruthy();
    });

    it('calls onGrant, not Linking.openSettings', () => {
      const spy = jest.spyOn(Linking, 'openSettings').mockImplementation(() => Promise.resolve());
      const { getByText, onGrant } = setup(true);

      fireEvent.press(getByText('Grant Permission'));

      expect(onGrant).toHaveBeenCalledTimes(1);
      expect(spy).not.toHaveBeenCalled();
    });
  });

  describe('when iOS has permanently denied (canAskAgain: false)', () => {
    it('routes to Settings instead of re-requesting', () => {
      // The regression: pressing here used to call requestPermission(), which
      // iOS silently ignores — leaving the user on a button that does nothing.
      const spy = jest.spyOn(Linking, 'openSettings').mockImplementation(() => Promise.resolve());
      const { getByText, onGrant } = setup(false);

      fireEvent.press(getByText('Open Settings'));

      expect(spy).toHaveBeenCalledTimes(1);
      expect(onGrant).not.toHaveBeenCalled();
    });

    it('does not offer the dead "Grant Permission" button', () => {
      const { queryByText } = setup(false);
      expect(queryByText('Grant Permission')).toBeNull();
    });

    it('tells the user access is off rather than merely required', () => {
      const { getByText } = setup(false);
      expect(getByText('Camera Access Is Off')).toBeTruthy();
    });
  });

  it('always leaves a way back out', () => {
    for (const canAskAgain of [true, false]) {
      const { getByText, onCancel } = setup(canAskAgain);
      fireEvent.press(getByText('Go Back'));
      expect(onCancel).toHaveBeenCalledTimes(1);
    }
  });
});
