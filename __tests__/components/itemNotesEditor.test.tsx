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
import { render, screen, fireEvent } from '@testing-library/react-native';

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

/**
 * Typing a note and leaving must not silently discard it.
 *
 * Reported as "the notes on the item card dont persist because after making a
 * note it doesnt hold or appear after clicking to other screens" — note the
 * wording: after MAKING a note, not after saving one.
 *
 * onSaveNotes had exactly ONE caller: the Save button's own handler. No blur
 * save, no unmount save, no autosave. So text typed and not explicitly saved
 * lived only in React state and went with the screen.
 *
 * This is the same shape as the bug this component was originally written to
 * fix — a "Notes saved locally" toast over a writer that wrote nothing. That
 * fix made the WRITE real and left the DISCARD in place.
 */
describe('ItemNotesEditor — leaving the field', () => {
  const input = () => screen.getByLabelText('Item notes');

  it('saves on blur when there are unsaved changes', () => {
    const onSaveNotes = jest.fn();
    const onChangeNotes = jest.fn();
    const { rerender } = render(
      <ItemNotesEditor notes="" onChangeNotes={onChangeNotes} onSaveNotes={onSaveNotes} onFocus={jest.fn()} />,
    );
    // Type through the INPUT, not by re-rendering with a new prop. The
    // component distinguishes "the server value arrived" from "the member
    // typed" by whether onChangeText fired, so a prop-only simulation tests a
    // path no person can take — and passed for the wrong reason.
    fireEvent.changeText(input(), 'a note I typed');
    expect(onChangeNotes).toHaveBeenCalledWith('a note I typed');
    // The parent owns the text, so it comes back down as a prop.
    rerender(
      <ItemNotesEditor notes="a note I typed" onChangeNotes={onChangeNotes} onSaveNotes={onSaveNotes} onFocus={jest.fn()} />,
    );
    fireEvent(input(), 'blur');
    expect(onSaveNotes).toHaveBeenCalledTimes(1);
  });

  it('does NOT save on blur when nothing changed', () => {
    const onSaveNotes = jest.fn();
    const { rerender } = render(
      <ItemNotesEditor notes="" onChangeNotes={jest.fn()} onSaveNotes={onSaveNotes} onFocus={jest.fn()} />,
    );
    rerender(
      <ItemNotesEditor notes="from the server" onChangeNotes={jest.fn()} onSaveNotes={onSaveNotes} onFocus={jest.fn()} />,
    );
    // Baseline adopted from the server value — merely focusing and leaving
    // must not write back what is already stored.
    fireEvent(input(), 'blur');
    expect(onSaveNotes).not.toHaveBeenCalled();
  });
});
