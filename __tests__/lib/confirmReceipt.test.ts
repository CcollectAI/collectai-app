/**
 * "I received it" completed a trade in one tap (walked 2026-10-16). Vinted asks
 * "Everything is OK" vs "I have an issue"; only OK may complete.
 */
import { Alert } from 'react-native';
import { askBuyerToConfirmReceipt } from '@/lib/confirmReceipt';

const t = ((_k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? _k) as never;

it('completes only on "Everything is OK"; "I have an issue" goes to the seller', () => {
  const spy = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  const onEverythingOk = jest.fn();
  const onIssue = jest.fn();
  askBuyerToConfirmReceipt({ t, onEverythingOk, onIssue });
  const [, body, buttons] = spy.mock.calls[0] as [string, string, { text: string; onPress?: () => void }[]];
  expect(body).toMatch(/can't be undone/);
  expect(buttons).toHaveLength(3); // Android shows at most three
  buttons.find((b) => b.text === 'I have an issue')!.onPress!();
  expect(onIssue).toHaveBeenCalled();
  expect(onEverythingOk).not.toHaveBeenCalled();
  buttons.find((b) => b.text === 'Everything is OK')!.onPress!();
  expect(onEverythingOk).toHaveBeenCalledTimes(1);
  expect(buttons.find((b) => b.text === 'Not yet')!.onPress).toBeUndefined();
});
