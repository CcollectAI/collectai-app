import { ActionSheetIOS, Alert, Platform } from 'react-native';

/**
 * Cross-platform action sheet picker.
 * On iOS uses ActionSheetIOS, on Android falls back to Alert.alert buttons.
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
