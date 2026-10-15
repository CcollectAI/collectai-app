import { ActionSheetIOS, Alert, Platform } from 'react-native';
import { presentActionSheet } from '@/components/ActionSheetHost';
import { logger } from '@/lib/logger';

/**
 * Cross-platform action sheet picker.
 * On iOS uses ActionSheetIOS. On Android it uses ActionSheetHost — NOT Alert.alert,
 * which renders at most three buttons and silently drops the rest (2026-10-15).
 *
 * @param title   The title shown at the top of the sheet.
 * @param options The selectable option labels (Cancel is added automatically).
 * @param onSelect Called with the zero-based index of the selected option.
 */
export function showActionSheet(
  title: string,
  options: string[],
  onSelect: (index: number) => void,
  onCancel?: () => void,
): void {
  if (Platform.OS === 'ios') {
    ActionSheetIOS.showActionSheetWithOptions(
      { options: ['Cancel', ...options], cancelButtonIndex: 0, title },
      (buttonIndex) => {
        if (buttonIndex > 0) {
          onSelect(buttonIndex - 1);
        } else {
          onCancel?.();
        }
      },
    );
  } else {
    if (presentActionSheet({ title, options, onSelect, onCancel })) return;
    // No host mounted (should not happen in the app — app/_layout.tsx mounts
    // one). Alert is only honest up to two options plus Cancel.
    if (options.length > 2) {
      logger.error('[actionSheet] no ActionSheetHost mounted; Alert drops options beyond 3 buttons', title);
    }
    // alert-buttons-ok: only reached with no ActionSheetHost mounted (logged above).
    Alert.alert(
      title,
      undefined,
      [
        ...options.map((label, i) => ({ text: label, onPress: () => onSelect(i) })),
        { text: 'Cancel', style: 'cancel' as const, onPress: onCancel },
      ],
    );
  }
}
