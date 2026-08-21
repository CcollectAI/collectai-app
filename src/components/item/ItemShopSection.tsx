/**
 * ItemShopSection — where to buy this item, on the marketplaces we can link to.
 *
 * ONE control, not a wall of chips (2026-08-20). It used to render a wrapping
 * row of bordered pills, one per source, so an item matched on six
 * marketplaces spent a whole block of the screen on six near-identical
 * outlines that all do the same thing. Reported as wanting "a dropdown or
 * something better visually than all the chips".
 *
 * The list itself did not shrink — it moved into a sheet, where each
 * marketplace gets a full-width row it can be read on instead of a pill it has
 * to be truncated into. Same reasoning as the watchlist card
 * (docs/ui-playbook.md, "A list card is a reference row, not a call to
 * action"): a repeated control set collapses to one action plus a list.
 *
 * `BottomSheetModal` is the app's existing sheet, the one ShareToChatSheet
 * uses — a second sheet idiom on the same screen would be the "three card
 * idioms in a row" bug in another costume.
 */
import React, { useCallback, useState } from 'react';
import { View, Text, StyleSheet, Linking, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { fireHaptic, HapticIntent } from '@/haptics';
import { AnimatedPressable } from '@/motion';
import { BottomSheetModal } from '@/components/BottomSheetModal';
import { radius, text, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

interface AffiliateLink {
  source: string;
  url: string;
  affiliate_url: string;
  label: string;
}

interface ItemShopSectionProps {
  affiliateLinks: AffiliateLink[];
}

export const ItemShopSection = React.memo(function ItemShopSection({ affiliateLinks }: ItemShopSectionProps) {
  const { colors: theme } = useAppTheme();
  const { settings } = useSettings();
  const [open, setOpen] = useState(false);

  const openLink = useCallback(
    (link: AffiliateLink) => {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      Linking.openURL(link.affiliate_url).catch((err) =>
        // logger.error, not warn: warn is stripped in release, which is exactly
        // where a link that silently does nothing would be invisible.
        logger.error('[ItemDetail] Failed to open affiliate URL', err),
      );
      setOpen(false);
    },
    [settings.hapticsEnabled],
  );

  if (affiliateLinks.length === 0) return null;

  // One marketplace does not need a sheet to choose from — it opens straight.
  const single = affiliateLinks.length === 1 ? affiliateLinks[0] : null;

  return (
    <View style={[styles.sectionBlock, { borderTopColor: theme.border }]}>
      <AnimatedPressable
        onPress={() => {
          if (single) { openLink(single); return; }
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          setOpen(true);
        }}
        style={[styles.trigger, { borderColor: theme.border }]}
        accessibilityRole="button"
        accessibilityLabel={
          single ? `Shop this item on ${single.label}` : `Shop this item — ${affiliateLinks.length} marketplaces`
        }
      >
        <Ionicons name="bag-handle-outline" size={18} color={theme.accent} />
        <Text style={[styles.triggerText, { color: theme.text }]} numberOfLines={1}>
          Shop this item
        </Text>
        <Text style={[styles.triggerMeta, { color: theme.muted }]} numberOfLines={1}>
          {single ? single.label : `${affiliateLinks.length} places`}
        </Text>
        <Ionicons name={single ? 'open-outline' : 'chevron-down'} size={16} color={theme.muted} />
      </AnimatedPressable>

      <BottomSheetModal
        visible={open}
        onClose={() => setOpen(false)}
        title="Shop this item"
        colors={theme}
        maxHeight="60%"
      >
        <ScrollView contentContainerStyle={styles.sheet}>
          {affiliateLinks.map((link) => (
            <AnimatedPressable
              key={link.source}
              onPress={() => openLink(link)}
              style={[styles.sheetRow, { borderColor: theme.border }]}
              accessibilityRole="link"
              accessibilityLabel={`Open ${link.label}`}
            >
              <Ionicons name="storefront-outline" size={18} color={theme.accent} />
              <Text style={[styles.sheetRowText, { color: theme.text }]} numberOfLines={1}>
                {link.label}
              </Text>
              <Ionicons name="open-outline" size={16} color={theme.muted} />
            </AnimatedPressable>
          ))}
        </ScrollView>
      </BottomSheetModal>
    </View>
  );
});

const styles = StyleSheet.create({
  sectionBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  // The label takes the room, the count sits beside it — `flex: 1` on the
  // label rather than on the row's last child, so a long marketplace name
  // truncates instead of pushing the chevron off the edge.
  triggerText: { flex: 1, fontSize: text.md, fontWeight: fontWeight.semibold },
  triggerMeta: { fontSize: text.sm, flexShrink: 1 },
  sheet: { padding: 16, paddingBottom: 32, gap: 10 },
  sheetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  sheetRowText: { flex: 1, fontSize: text.md, fontWeight: fontWeight.medium },
});
