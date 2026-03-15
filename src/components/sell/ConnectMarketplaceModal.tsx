/**
 * ConnectMarketplaceModal — Modal for connecting an external marketplace account.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TextInput,
  ScrollView,
  Pressable,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight, gap } from '@/theme/tokens';
import type { MarketplaceId } from '@/data/types';

const MARKETPLACE_CONFIG: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  ebay: { label: 'eBay', icon: 'cart-outline', color: '#E53238' },
  mercari: { label: 'Mercari', icon: 'storefront-outline', color: '#4DC8F0' },
  cardmarket: { label: 'Cardmarket', icon: 'card-outline', color: '#1A3C7D' },
  stockx: { label: 'StockX', icon: 'trending-up-outline', color: '#006340' },
  discogs: { label: 'Discogs', icon: 'disc-outline', color: '#333333' },
  bricklink: { label: 'BrickLink', icon: 'cube-outline', color: '#D01012' },
};

const CONNECT_MARKETPLACES: MarketplaceId[] = ['ebay', 'mercari', 'cardmarket', 'stockx', 'discogs', 'bricklink'];

interface ConnectMarketplaceModalProps {
  visible: boolean;
  onClose: () => void;
  selectedMp: MarketplaceId;
  onMpChange: (mp: MarketplaceId) => void;
  sellerName: string;
  onSellerNameChange: (name: string) => void;
  connecting: boolean;
  onConnect: () => void;
}

export const ConnectMarketplaceModal = React.memo(function ConnectMarketplaceModal({
  visible,
  onClose,
  selectedMp,
  onMpChange,
  sellerName,
  onSellerNameChange,
  connecting,
  onConnect,
}: ConnectMarketplaceModalProps) {
  const { colors } = useAppTheme();

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.modalOverlay}>
        <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Connect Marketplace</Text>
            <AnimatedPressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close">
              <Ionicons name="close" size={24} color={colors.muted} />
            </AnimatedPressable>
          </View>
          <Text style={[styles.modalLabel, { color: colors.text }]}>Marketplace</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
            {CONNECT_MARKETPLACES.map((mp) => {
              const cfg = MARKETPLACE_CONFIG[mp];
              const isActive = selectedMp === mp;
              return (
                <Pressable key={mp} onPress={() => onMpChange(mp)} style={[styles.mpChip, { borderColor: isActive ? cfg?.color ?? colors.accent : colors.border }, isActive && { backgroundColor: (cfg?.color ?? colors.accent) + '15' }]}>
                  <Text style={[styles.mpChipText, { color: isActive ? cfg?.color ?? colors.accent : colors.muted }]}>{cfg?.label ?? mp}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          <Text style={[styles.modalLabel, { color: colors.text }]}>Seller Name (optional)</Text>
          <TextInput
            style={[styles.modalInput, { backgroundColor: colors.background, borderColor: colors.border, color: colors.text }]}
            value={sellerName}
            onChangeText={onSellerNameChange}
            placeholder="Your seller username"
            placeholderTextColor={colors.muted}
            returnKeyType="done"
          />
          <AnimatedPressable
            style={[styles.createBtn, { backgroundColor: colors.accent }, connecting && { opacity: 0.7 }]}
            onPress={onConnect}
            disabled={connecting}
            accessibilityRole="button"
            accessibilityLabel="Connect account"
          >
            {connecting ? <ActivityIndicator size="small" color={colors.accentText} /> : <Text style={[styles.createBtnText, { color: colors.accentText }]}>Connect</Text>}
          </AnimatedPressable>
        </View>
      </View>
    </Modal>
  );
});

const styles = StyleSheet.create({
  modalOverlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.4)' },
  modalContent: { borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: 20, paddingBottom: 40 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: text.xl, fontWeight: fontWeight.bold },
  modalLabel: { fontSize: text.md, fontWeight: fontWeight.semibold, marginBottom: 6, marginTop: gap.md },
  modalInput: { borderRadius: radius.sm, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 10, fontSize: text.lg, marginBottom: gap.md },
  mpChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.md, borderWidth: 1, marginRight: gap.md },
  mpChipText: { fontSize: text.sm, fontWeight: fontWeight.semibold },
  createBtn: { borderRadius: radius.md, paddingVertical: 14, alignItems: 'center', justifyContent: 'center' },
  createBtnText: { fontSize: text.lg, fontWeight: fontWeight.bold },
});
