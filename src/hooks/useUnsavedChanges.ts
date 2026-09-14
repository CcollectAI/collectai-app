/**
 * useUnsavedChanges — intercept back navigation when form has unsaved changes.
 *
 * Uses React Navigation's beforeRemove event to show a confirmation alert
 * before discarding changes.
 */

import { useEffect } from 'react';
import { Alert } from 'react-native';
import { useNavigation } from 'expo-router';
import { useTranslation } from 'react-i18next';

interface UseUnsavedChangesOptions {
  /** Whether the form has unsaved changes */
  isDirty: boolean;
  /** Called when the user confirms discard */
  onDiscard?: () => void;
}

export function useUnsavedChanges({ isDirty, onDiscard }: UseUnsavedChangesOptions) {
  const navigation = useNavigation();
  const { t } = useTranslation();

  useEffect(() => {
    if (!isDirty) return;

    const unsubscribe = navigation.addListener('beforeRemove', (e) => {
      // Block the navigation
      e.preventDefault();

      Alert.alert(
        t('common.unsaved_title', { defaultValue: 'Unsaved Changes' }),
        t('common.unsaved_message', { defaultValue: 'You have unsaved changes. Discard them and leave?' }),
        [
          { text: t('common.cancel', { defaultValue: 'Cancel' }), style: 'cancel' },
          {
            text: t('common.discard', { defaultValue: 'Discard' }),
            style: 'destructive',
            onPress: () => {
              onDiscard?.();
              // Allow the blocked navigation to proceed
              navigation.dispatch(e.data.action);
            },
          },
        ],
      );
    });

    return unsubscribe;
  }, [isDirty, navigation, onDiscard, t]);
}
