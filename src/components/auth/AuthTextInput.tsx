/**
 * AuthTextInput — Themed input with floating label, icon prefix, and animated focus state.
 */

import React, { forwardRef, useRef, useState } from 'react';
import {
  Animated,
  StyleSheet,
  TextInput,
  TextInputProps,
  View,
  Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

export interface AuthTextInputProps
  extends Pick<
    TextInputProps,
    | 'value'
    | 'onChangeText'
    | 'secureTextEntry'
    | 'keyboardType'
    | 'autoComplete'
    | 'returnKeyType'
    | 'onSubmitEditing'
    | 'autoFocus'
    | 'testID'
    | 'autoCapitalize'
  > {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
}

export const AuthTextInput = forwardRef<TextInput, AuthTextInputProps>(
  function AuthTextInput(
    { label, icon, value, onChangeText, secureTextEntry, ...rest },
    ref,
  ) {
    const { colors } = useAppTheme();
    const { settings } = useSettings();
    const [focused, setFocused] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const hasValue = !!value && value.length > 0;

    // Floating label animation
    const labelAnim = useRef(new Animated.Value(hasValue ? 1 : 0)).current;

    const handleFocus = () => {
      setFocused(true);
      Animated.timing(labelAnim, {
        toValue: 1,
        duration: 150,
        useNativeDriver: false,
      }).start();
    };

    const handleBlur = () => {
      setFocused(false);
      if (!hasValue) {
        Animated.timing(labelAnim, {
          toValue: 0,
          duration: 150,
          useNativeDriver: false,
        }).start();
      }
    };

    const labelTranslateY = labelAnim.interpolate({
      inputRange: [0, 1],
      outputRange: [0, -20],
    });
    const labelFontSize = labelAnim.interpolate({
      inputRange: [0, 1],
      outputRange: [16, 12],
    });

    const borderColor = focused ? colors.brand.base : colors.border;
    const iconColor = focused ? colors.brand.dark : colors.muted;

    return (
      <View
        style={[
          styles.container,
          {
            backgroundColor: colors.card,
            borderColor,
            ...(focused && {
              shadowColor: colors.brand.base,
              shadowOpacity: 0.2,
              shadowRadius: 8,
              shadowOffset: { width: 0, height: 0 },
              elevation: 4,
            }),
          },
        ]}
      >
        <Ionicons name={icon} size={20} color={iconColor} style={styles.icon} />

        <View style={styles.inputArea}>
          <Animated.Text
            style={[
              styles.label,
              {
                color: focused ? colors.brand.dark : colors.muted,
                transform: [{ translateY: labelTranslateY }],
                fontSize: labelFontSize,
              },
            ]}
            pointerEvents="none"
          >
            {label}
          </Animated.Text>
          <TextInput
            ref={ref}
            style={[styles.input, { color: colors.text }]}
            value={value}
            onChangeText={onChangeText}
            secureTextEntry={secureTextEntry && !showPassword}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholderTextColor="transparent"
            accessibilityLabel={label}
            {...rest}
          />
        </View>

        {secureTextEntry && (
          <Pressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              setShowPassword((p) => !p);
            }}
            style={styles.eyeBtn}
            hitSlop={8}
            accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
          >
            <Ionicons
              name={showPassword ? 'eye-off-outline' : 'eye-outline'}
              size={20}
              color={colors.muted}
            />
          </Pressable>
        )}
      </View>
    );
  },
);

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 56,
    borderRadius: 16,
    borderWidth: 1.5,
    paddingHorizontal: 14,
  },
  icon: {
    marginRight: 10,
  },
  inputArea: {
    flex: 1,
    justifyContent: 'center',
    height: '100%',
  },
  label: {
    position: 'absolute',
    left: 0,
  },
  input: {
    fontSize: 16,
    paddingTop: 8,
    height: '100%',
  },
  eyeBtn: {
    padding: 4,
    marginLeft: 4,
  },
});
