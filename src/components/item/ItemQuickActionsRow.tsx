/**
 * ItemQuickActionsRow — Edit / Share / List for Sale buttons shown below image.
 */
import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, Share, Platform } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight as fw, gap } from '@/theme/tokens';

interface ItemQuickActionsRowProps {
  editableName: string;
  editableValue: string;
  /** Item photo (local file:// capture or remote catalog/storage URL). Shared as an attachment. */
  imageUri?: string | null;
  isForSale: boolean;
  onEdit: () => void;
  onListForSale: () => void;
}

const toNum = (value: string | number | undefined | null): number | undefined => {
  if (value === undefined || value === null || value === '') return undefined;
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return undefined;
  return num;
};

const MIME_BY_EXT: Record<string, string> = {
  jpg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
};

/**
 * Sharing the item picture needs a LOCAL file. A camera capture is already a
 * `file://` uri; a catalog/storage image is a remote URL we download to cache
 * first. Returns null (→ caller falls back to text-only share) if there is no
 * usable image or the download fails.
 */
async function resolveLocalImage(
  uri: string,
): Promise<{ uri: string; mime: string } | null> {
  try {
    if (uri.startsWith('file://')) {
      const ext = (uri.match(/\.(jpe?g|png|webp)$/i)?.[1] || 'jpg').toLowerCase();
      const norm = ext === 'jpeg' ? 'jpg' : ext;
      return { uri, mime: MIME_BY_EXT[norm] || 'image/jpeg' };
    }
    if (!/^https?:\/\//i.test(uri)) return null;
    const rawExt = (uri.split('?')[0].match(/\.(jpe?g|png|webp)$/i)?.[1] || 'jpg').toLowerCase();
    const ext = rawExt === 'jpeg' ? 'jpg' : rawExt;
    const target = `${FileSystem.cacheDirectory}sparrow-share.${ext}`;
    const { uri: localUri } = await FileSystem.downloadAsync(uri, target);
    return { uri: localUri, mime: MIME_BY_EXT[ext] || 'image/jpeg' };
  } catch {
    return null;
  }
}

export const ItemQuickActionsRow = React.memo(function ItemQuickActionsRow(props: ItemQuickActionsRowProps) {
  const { colors: theme } = useAppTheme();
  const { editableName, editableValue, imageUri, isForSale, onEdit, onListForSale } = props;
  const [busy, setBusy] = useState(false);

  const handleShare = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      const val = toNum(editableValue);
      // Caption a recipient sees alongside the picture, plus a tappable link.
      const message =
        `Check out my ${editableName} on Sparrow Collect` +
        (val ? `\nEstimated value: ${formatPrice(val)}` : '') +
        `\n\nhttps://sparrowcollect.com`;

      // Attach the item photo so it lands in WhatsApp / Messages as a card
      // with the picture, not just a line of text.
      const image = imageUri ? await resolveLocalImage(imageUri) : null;

      if (image && Platform.OS === 'ios') {
        // iOS share sheet carries BOTH the image (url) and the caption
        // (message) into WhatsApp / Messages.
        await Share.share({ url: image.uri, message });
      } else if (image && (await Sharing.isAvailableAsync())) {
        // Android's share intent can't pair a caption with an image, so we
        // send the picture (the point of the share) via expo-sharing.
        await Sharing.shareAsync(image.uri, {
          mimeType: image.mime,
          dialogTitle: `Share ${editableName}`,
        });
      } else {
        // No photo (or download failed) — fall back to text + link.
        await Share.share({ message });
      }
    } catch {
      // User cancelled or share failed
    } finally {
      setBusy(false);
    }
  }, [busy, editableName, editableValue, imageUri]);

  return (
    <View style={styles.quickActionsRow}>
      <AnimatedPressable
        onPress={onEdit}
        disabled={busy}
        style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }, busy && { opacity: 0.5 }]}
        accessibilityRole="button"
        accessibilityLabel="Edit item details"
      >
        <Ionicons name="create-outline" size={18} color={theme.accent} />
        <Text style={[styles.quickActionLabel, { color: theme.text }]}>Edit</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={handleShare}
        disabled={busy}
        style={[styles.quickActionBtn, { backgroundColor: theme.card, borderColor: theme.border }, busy && { opacity: 0.5 }]}
        accessibilityRole="button"
        accessibilityLabel="Share this item"
      >
        <Ionicons name="share-outline" size={18} color={theme.accent} />
        <Text style={[styles.quickActionLabel, { color: theme.text }]}>Share</Text>
      </AnimatedPressable>
      {!isForSale ? (
        <AnimatedPressable
          onPress={onListForSale}
          disabled={busy}
          style={[styles.quickActionBtn, { backgroundColor: theme.accent + '12', borderColor: theme.accent }, busy && { opacity: 0.5 }]}
          accessibilityRole="button"
          accessibilityLabel="List this item for sale on marketplaces"
        >
          <Ionicons name="storefront-outline" size={18} color={theme.accent} />
          <Text style={[styles.quickActionLabel, { color: theme.accent }]}>List for Sale</Text>
        </AnimatedPressable>
      ) : (
        <View
          style={[styles.quickActionBtn, { backgroundColor: theme.successBg, borderColor: theme.success }]}
          accessibilityRole="text"
          accessibilityLabel="Item is currently listed for sale"
        >
          <Ionicons name="pricetag" size={18} color={theme.success} />
          <Text style={[styles.quickActionLabel, { color: theme.success }]}>Listed</Text>
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  quickActionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: gap.md,
    marginBottom: 4,
  },
  quickActionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: gap.sm,
    minWidth: 70,
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  quickActionLabel: {
    fontSize: text.md,
    fontWeight: fw.semibold,
  },
});
