import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { Text } from 'react-native';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: ({ name, ...props }: any) => {
    const { View } = require('react-native');
    return <View testID={`icon-${name}`} {...props} />;
  },
}));

import { BottomSheetModal } from '../../src/components/BottomSheetModal';

const MOCK_COLORS = {
  background: '#FFFFFF',
  text: '#0F172A',
  border: '#E2E8F0',
};

describe('BottomSheetModal', () => {
  it('renders children when visible is true', () => {
    render(
      <BottomSheetModal
        visible={true}
        onClose={jest.fn()}
        title="Test Title"
        colors={MOCK_COLORS}
      >
        <Text>Child content</Text>
      </BottomSheetModal>,
    );

    expect(screen.getByText('Child content')).toBeTruthy();
  });

  it('renders the title text', () => {
    render(
      <BottomSheetModal
        visible={true}
        onClose={jest.fn()}
        title="My Sheet Title"
        colors={MOCK_COLORS}
      >
        <Text>Body</Text>
      </BottomSheetModal>,
    );

    expect(screen.getByText('My Sheet Title')).toBeTruthy();
  });

  it('does not render children when visible is false', () => {
    render(
      <BottomSheetModal
        visible={false}
        onClose={jest.fn()}
        title="Hidden"
        colors={MOCK_COLORS}
      >
        <Text>Should not appear</Text>
      </BottomSheetModal>,
    );

    expect(screen.queryByText('Should not appear')).toBeNull();
  });

  it('calls onClose when the close icon is pressed', () => {
    const onClose = jest.fn();
    render(
      <BottomSheetModal
        visible={true}
        onClose={onClose}
        title="Closeable"
        colors={MOCK_COLORS}
      >
        <Text>Content</Text>
      </BottomSheetModal>,
    );

    // The close button renders an Ionicons "close" icon
    const closeIcon = screen.getByTestId('icon-close');
    // Press the parent Pressable (close icon's container)
    fireEvent.press(closeIcon);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders the close icon', () => {
    render(
      <BottomSheetModal
        visible={true}
        onClose={jest.fn()}
        title="With Close"
        colors={MOCK_COLORS}
      >
        <Text>Inner</Text>
      </BottomSheetModal>,
    );

    expect(screen.getByTestId('icon-close')).toBeTruthy();
  });

  it('renders headerRight when provided', () => {
    render(
      <BottomSheetModal
        visible={true}
        onClose={jest.fn()}
        title="With Action"
        colors={MOCK_COLORS}
        headerRight={<Text>Save</Text>}
      >
        <Text>Body</Text>
      </BottomSheetModal>,
    );

    expect(screen.getByText('Save')).toBeTruthy();
  });

  it('renders in pageSheet mode when specified', () => {
    render(
      <BottomSheetModal
        visible={true}
        onClose={jest.fn()}
        title="Page Sheet"
        colors={MOCK_COLORS}
        mode="pageSheet"
      >
        <Text>Page content</Text>
      </BottomSheetModal>,
    );

    expect(screen.getByText('Page Sheet')).toBeTruthy();
    expect(screen.getByText('Page content')).toBeTruthy();
  });
});
