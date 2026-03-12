/**
 * Import from URL screen — paste a marketplace listing URL to auto-import item details.
 * Moved from barcode-scan mode toggle to its own dedicated screen.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Keyboard,
} from 'react-native';
import { router, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { collectorsApi } from '@/api/collectorsApi';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import logger from '@/utils/logger';

function ImportUrlScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const [urlInput, setUrlInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    const trimmed = urlInput.trim();
    if (!trimmed || !trimmed.startsWith('http')) {
      showToast({ message: 'Please enter a valid URL starting with https://', type: 'warning' });
      return;
    }

    Keyboard.dismiss();
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setIsSubmitting(true);

    try {
      const intake = await collectorsApi.processIntakeUrl(trimmed);

      // Navigate to add-manual with prefilled data from URL import
      router.replace({
        pathname: '/add-manual',
        params: {
          prefillName: intake.name || '',
          prefillCategory: intake.category_id || '',
          prefillImageUrl: intake.image_url || '',
          prefillSource: 'url',
          prefillSourceUrl: trimmed,
        },
      });
    } catch (err) {
      logger.error('[ImportUrl] URL import error:', err);
      showToast({ message: 'Could not import from this URL. Check the link and try again.', type: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Import from URL' }} />
      <KeyboardAvoidingView
        style={styles.content}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 100 : 20}
      >
        <View style={[styles.card, { backgroundColor: colors.card }]}>
          <View style={[styles.iconCircle, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name="link-outline" size={32} color={colors.accent} />
          </View>
          <Text style={[styles.title, { color: colors.text }]}>
            Paste a marketplace link
          </Text>
          <Text style={[styles.helper, { color: colors.muted }]}>
            We'll extract the item details automatically from the listing.
          </Text>
          <TextInput
            style={[styles.urlInput, {
              backgroundColor: colors.background,
              borderColor: colors.border,
              color: colors.text,
            }]}
            placeholder="https://ebay.com/itm/..."
            placeholderTextColor={colors.muted}
            value={urlInput}
            onChangeText={setUrlInput}
            keyboardType="url"
            autoCapitalize="none"
            autoCorrect={false}
            autoFocus
            returnKeyType="go"
            onSubmitEditing={handleSubmit}
            accessibilityLabel="Marketplace URL"
          />
          <AnimatedPressable
            style={[styles.submitBtn, {
              backgroundColor: colors.accent,
              opacity: !urlInput.startsWith('http') || isSubmitting ? 0.5 : 1,
            }]}
            onPress={handleSubmit}
            disabled={!urlInput.startsWith('http') || isSubmitting}
            accessibilityLabel="Import from URL"
            accessibilityRole="button"
          >
            {isSubmitting ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="download-outline" size={20} color="#fff" />
                <Text style={styles.submitBtnText}>Import Item</Text>
              </>
            )}
          </AnimatedPressable>
        </View>

        <View style={[styles.sitesCard, { backgroundColor: colors.card }]}>
          <Text style={[styles.sitesTitle, { color: colors.muted }]}>Supported sites</Text>
          <Text style={[styles.sitesText, { color: colors.muted }]}>
            eBay, Mercari, StockX, TCGPlayer, BrickLink, Discogs, MyFigureCollection, Ktown4u, Weverse
          </Text>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

export default function ImportUrlScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Import URL">
      <ImportUrlScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    borderRadius: 20,
    padding: 28,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 8,
  },
  helper: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  urlInput: {
    width: '100%',
    height: 52,
    borderRadius: 12,
    borderWidth: 1.5,
    paddingHorizontal: 16,
    fontSize: 15,
    marginBottom: 16,
  },
  submitBtn: {
    alignSelf: 'stretch',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 52,
    borderRadius: 14,
    overflow: 'hidden',
    shadowColor: '#81D8D0',
    shadowOpacity: 0.3,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
  submitBtnText: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  sitesCard: {
    marginTop: 16,
    borderRadius: 14,
    padding: 16,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  sitesTitle: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sitesText: {
    fontSize: 13,
    lineHeight: 18,
  },
});
