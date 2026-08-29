/**
 * ItemNotesEditor — the Save button's baseline.
 *
 * The notes value arrives from the server AFTER mount, so the value this
 * component is constructed with is almost always ''. The resync effect had an
 * EMPTY dependency array while the comment beside it read "we intentionally
 * depend on `notes` only" — the comment described the intent and the code ran
 * once. `lastSaved` stayed '' forever, so `hasChanges` was permanently true.
 *
 * Effect: opening an item that already has notes showed an enabled Save button
 * with nothing to save, inviting a write-back of the stored value.
 */
import React from 'react';
import { render, screen } from '@testing-library/react-native';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: ({ name, ...props }: any) => {
    const { View } = require('react-native');
    return <View testID={`icon-${name}`} {...props} />;
  },
}));
jest.mock('../../src/hooks/useAppTheme', () => ({
  useAppTheme: () => ({
    colors: {
      background: '#FFFFFF', card: '#FFFFFF', text: '#0F172A',
      muted: '#64748B', border: '#E2E8F0', accent: '#81D8D0',
      accentText: '#0b1120',
    },
    isDark: false,
  }),
}));

import { ItemNotesEditor } from '../../src/components/item/ItemNotesEditor';

const setup = (notes: string) =>
  render(
    <ItemNotesEditor
      notes={notes}
      onChangeNotes={jest.fn()}
      onSaveNotes={jest.fn()}
      onFocus={jest.fn()}
    />,
  );

const saveBtn = () => screen.UNSAFE_getAllByProps({ accessibilityRole: 'button' })
  .find((n: any) => typeof n.props.disabled === 'boolean');

describe('ItemNotesEditor', () => {
  it('renders the notes it is given', () => {
    setup('bought at a fair in Utrecht');
    expect(screen.getByDisplayValue('bought at a fair in Utrecht')).toBeTruthy();
  });

  it('Save is DISABLED when the server value arrives and nothing was typed', () => {
    // The real sequence: mount empty, then the fetch lands.
    const { rerender } = render(
      <ItemNotesEditor notes="" onChangeNotes={jest.fn()} onSaveNotes={jest.fn()} onFocus={jest.fn()} />,
    );
    rerender(
      <ItemNotesEditor notes="from the server" onChangeNotes={jest.fn()} onSaveNotes={jest.fn()} onFocus={jest.fn()} />,
    );
    expect(saveBtn()?.props.disabled).toBe(true);
  });

  it('Save is ENABLED once the text differs from the saved baseline', () => {
    const { rerender } = render(
      <ItemNotesEditor notes="" onChangeNotes={jest.fn()} onSaveNotes={jest.fn()} onFocus={jest.fn()} />,
    );
    rerender(
      <ItemNotesEditor notes="from the server" onChangeNotes={jest.fn()} onSaveNotes={jest.fn()} onFocus={jest.fn()} />,
    );
    rerender(
      <ItemNotesEditor notes="from the server, edited" onChangeNotes={jest.fn()} onSaveNotes={jest.fn()} onFocus={jest.fn()} />,
    );
    expect(saveBtn()?.props.disabled).toBe(false);
  });
});
