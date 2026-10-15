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

  describe('Android after a one-time grant expired (canAskAgain: false, 2026-10-15)', () => {
    const { Platform } = require('react-native');
    const realOS = Platform.OS;
    beforeEach(() => { Platform.OS = 'android'; });
    afterEach(() => { Platform.OS = realOS; });

    it('asks first, and does not open Settings when the ask is granted', async () => {
      const spy = jest.spyOn(Linking, 'openSettings').mockImplementation(() => Promise.resolve());
      const onGrant = jest.fn().mockResolvedValue({ granted: true });
      const { getByText } = render(
        <PermissionScreen onGrant={onGrant} onCancel={jest.fn()} hapticsEnabled={false}
          canAskAgain={false} colors={colors} />,
      );
      fireEvent.press(getByText('Open Settings'));
      await new Promise((r) => setImmediate(r));
      expect(onGrant).toHaveBeenCalledTimes(1);
      expect(spy).not.toHaveBeenCalled();
    });

    it('opens Settings when Android still refuses', async () => {
      const spy = jest.spyOn(Linking, 'openSettings').mockImplementation(() => Promise.resolve());
      const onGrant = jest.fn().mockResolvedValue({ granted: false });
      const { getByText } = render(
        <PermissionScreen onGrant={onGrant} onCancel={jest.fn()} hapticsEnabled={false}
          canAskAgain={false} colors={colors} />,
      );
      fireEvent.press(getByText('Open Settings'));
      await new Promise((r) => setImmediate(r));
      expect(onGrant).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledTimes(1);
    });
  });

  it('always leaves a way back out', () => {
    // By accessibility LABEL, not by visible text. This asserted
    // `getByText('Go Back')` and went red when the copy moved to
    // `t('common.go_back')`, which renders "Go back" — so the suite was red
    // over a capital B while the escape hatch was present the whole time.
    // The guarantee worth asserting is that a labelled control exists and
    // calls onCancel, which is also what the member who most needs it gets.
    for (const canAskAgain of [true, false]) {
      const { getByLabelText, onCancel } = setup(canAskAgain);
      fireEvent.press(getByLabelText('Go back'));
      expect(onCancel).toHaveBeenCalledTimes(1);
    }
  });

  it('offers the caller\'s camera-free way forward, and only when given one', () => {
    // The barcode scanner's manual ISBN box needs no camera but sat behind
    // this screen: camera off = no way to type a code (walked 2026-10-15).
    const onPress = jest.fn();
    for (const canAskAgain of [true, false]) {
      onPress.mockClear();
      const { getByLabelText, unmount } = render(
        <PermissionScreen
          onGrant={jest.fn()}
          onCancel={jest.fn()}
          hapticsEnabled={false}
          canAskAgain={canAskAgain}
          secondaryAction={{ label: 'Type the code instead', onPress }}
          colors={colors}
        />,
      );
      fireEvent.press(getByLabelText('Type the code instead'));
      expect(onPress).toHaveBeenCalledTimes(1);
      unmount();
    }
    const { queryByLabelText } = setup(false);
    expect(queryByLabelText('Type the code instead')).toBeNull();
  });
});
