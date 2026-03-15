/**
 * Snapshot tests for Form components: FormField, SelectField, DateField.
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
    elevated: {
      shadowColor: '#000',
      shadowOpacity: 0.12,
      shadowRadius: 16,
      shadowOffset: { width: 0, height: 8 },
      elevation: 6,
    },
  },
  gap: { xxs: 2, xs: 4, sm: 6, md: 8, lg: 10, xl: 12 },
}));

jest.mock('../../src/hooks/useActionSheetPicker', () => ({
  showActionSheet: jest.fn(),
}));

jest.mock('../../src/motion', () => {
  const { Pressable } = require('react-native');
  return {
    AnimatedPressable: (props: any) => <Pressable {...props} />,
  };
});

// Import components after mocks
import { FormField } from '../../src/components/form/FormField';
import { SelectField } from '../../src/components/form/SelectField';
import { DateField } from '../../src/components/form/DateField';

// ---------------------------------------------------------------------------
// FormField
// ---------------------------------------------------------------------------

describe('FormField', () => {
  it('renders with basic props and matches snapshot', () => {
    const tree = render(
      <FormField label="Item Name" value="Charizard" onChangeText={jest.fn()} />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders the label text', () => {
    render(<FormField label="Title" value="" onChangeText={jest.fn()} />);
    expect(screen.getByText('Title')).toBeTruthy();
  });

  it('renders error state and matches snapshot', () => {
    const tree = render(
      <FormField
        label="Email"
        value=""
        onChangeText={jest.fn()}
        error="This field is required"
      />,
    );
    expect(screen.getByText('This field is required')).toBeTruthy();
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('renders required indicator', () => {
    render(
      <FormField label="Name" value="" onChangeText={jest.fn()} required />,
    );
    expect(screen.getByText('*')).toBeTruthy();
  });

  it('renders multiline variant', () => {
    const tree = render(
      <FormField
        label="Description"
        value="Some long text"
        onChangeText={jest.fn()}
        multiline
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// SelectField
// ---------------------------------------------------------------------------

describe('SelectField', () => {
  const options = [
    { label: 'Pokemon', value: 'pokemon' },
    { label: 'LEGO', value: 'lego' },
    { label: 'Watches', value: 'watches' },
  ];

  it('renders with options and matches snapshot', () => {
    const tree = render(
      <SelectField
        label="Category"
        value="pokemon"
        options={options}
        onChange={jest.fn()}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('displays selected option label', () => {
    render(
      <SelectField
        label="Category"
        value="lego"
        options={options}
        onChange={jest.fn()}
      />,
    );
    expect(screen.getByText('LEGO')).toBeTruthy();
  });

  it('displays placeholder when no value matches', () => {
    render(
      <SelectField
        label="Category"
        value=""
        options={options}
        onChange={jest.fn()}
        placeholder="Pick one..."
      />,
    );
    expect(screen.getByText('Pick one...')).toBeTruthy();
  });

  it('renders error text', () => {
    render(
      <SelectField
        label="Category"
        value=""
        options={options}
        onChange={jest.fn()}
        error="Selection required"
      />,
    );
    expect(screen.getByText('Selection required')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// DateField
// ---------------------------------------------------------------------------

describe('DateField', () => {
  it('renders with a date value and matches snapshot', () => {
    const tree = render(
      <DateField
        label="Purchase Date"
        value={new Date(2025, 5, 15)}
        onChange={jest.fn()}
      />,
    );
    expect(tree.toJSON()).toMatchSnapshot();
  });

  it('displays formatted date', () => {
    render(
      <DateField
        label="Date"
        value={new Date(2025, 0, 1)}
        onChange={jest.fn()}
      />,
    );
    expect(screen.getByText('2025-01-01')).toBeTruthy();
  });

  it('displays placeholder when value is null', () => {
    render(
      <DateField
        label="Date"
        value={null}
        onChange={jest.fn()}
        placeholder="Choose a date..."
      />,
    );
    expect(screen.getByText('Choose a date...')).toBeTruthy();
  });

  it('renders error text', () => {
    render(
      <DateField
        label="Date"
        value={null}
        onChange={jest.fn()}
        error="Date is required"
      />,
    );
    expect(screen.getByText('Date is required')).toBeTruthy();
  });
});
