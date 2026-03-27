/**
 * useUnsavedChanges — intercept back navigation when form has unsaved changes.
 *
 * Uses React Navigation's beforeRemove event to show a confirmation alert
 * before discarding changes.
 */

import { useEffect } from 'react';
import { Alert } from 'react-native';
import { useNavigation } from 'expo-router';

interface UseUnsavedChangesOptions {
  /** Whether the form has unsaved changes */
  isDirty: boolean;
  /** Called when the user confirms discard */
  onDiscard?: () => void;
}

export function useUnsavedChanges({ isDirty, onDiscard }: UseUnsavedChangesOptions) {
  const navigation = useNavigation();

  useEffect(() => {
    if (!isDirty) return;

    const unsubscribe = navigation.addListener('beforeRemove', (e) => {
      // Block the navigation
      e.preventDefault();

      Alert.alert(
        'Unsaved Changes',
        'You have unsaved changes. Discard them and leave?',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Discard',
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
  }, [isDirty, navigation, onDiscard]);
}
