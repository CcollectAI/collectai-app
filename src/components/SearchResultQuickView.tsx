/**
 * Quick-view bottom sheet overlay for marketplace search results.
 *
 * Shows item image, title, source, price, shipping info,
 * and action buttons (Open Listing, Share, Close).
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from "react";
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  Modal,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { formatPrice } from "@/lib/format";

// ── Exported types ──────────────────────────────────────────────────────

export type QuickViewItem = {
  name: string;
  value: number;
  source?: string;
  condition?: string;
  image_url?: string | null;
  externalUrl?: string;
  affiliateUrl?: string;
  secondaryPrice?: string | null;
  shippingHint?: string;
};

// ── Props ───────────────────────────────────────────────────────────────

interface SearchResultQuickViewProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    card: string;
  };
  visible: boolean;
  item: QuickViewItem | null;
  onClose: () => void;
  onOpenUrl: () => void;
  onShare: () => void;
}

// ── Component ───────────────────────────────────────────────────────────

function SearchResultQuickViewInner({
  theme,
  visible,
  item,
  onClose,
  onOpenUrl,
  onShare,
}: SearchResultQuickViewProps) {
  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <TouchableOpacity
        activeOpacity={1}
        onPress={onClose}
        style={s.quickViewOverlay}
      >
        <TouchableOpacity
          activeOpacity={1}
          style={[s.quickViewSheet, { backgroundColor: theme.card }]}
        >
          {item && (
            <>
              <View style={[s.quickViewHandle, { backgroundColor: theme.muted + "40" }]} />
              <View style={s.quickViewHeader}>
                {item.image_url ? (
                  <Image
                    source={{ uri: item.image_url }}
                    style={s.quickViewImage}
                  />
                ) : (
                  <View
                    style={[
                      s.quickViewImagePlaceholder,
                      { backgroundColor: theme.accent + "15" },
                    ]}
                  >
                    <Ionicons name="cart-outline" size={28} color={theme.accent} />
                  </View>
                )}
                <View style={s.quickViewInfo}>
                  <Text
                    style={[s.quickViewTitle, { color: theme.text }]}
                    numberOfLines={2}
                  >
                    {item.name}
                  </Text>
                  <Text style={[s.quickViewSource, { color: theme.muted }]}>
                    {item.source || "Marketplace"}
                    {item.condition ? ` \u00b7 ${item.condition}` : ""}
                  </Text>
                  <Text style={[s.quickViewPrice, { color: theme.accent }]}>
                    {formatPrice(item.value)}
                  </Text>
                  {item.secondaryPrice && (
                    <Text style={[s.quickViewSecondary, { color: theme.muted }]}>
                      {item.secondaryPrice}
                    </Text>
                  )}
                  {item.shippingHint && (
                    <Text style={[s.quickViewShipping, { color: theme.muted }]}>
                      {item.shippingHint}
                    </Text>
                  )}
                </View>
              </View>

              <View style={s.quickViewActions}>
                <TouchableOpacity
                  onPress={onOpenUrl}
                  style={[
                    s.quickViewBtn,
                    s.quickViewBtnPrimary,
                    { backgroundColor: theme.accent },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel="Open in browser"
                >
                  <Ionicons name="open-outline" size={18} color="#FFFFFF" />
                  <Text style={s.quickViewBtnPrimaryText}>Open Listing</Text>
                </TouchableOpacity>
                <View style={s.quickViewBtnRow}>
                  <TouchableOpacity
                    onPress={onShare}
                    style={[
                      s.quickViewBtnSecondary,
                      { borderColor: theme.border },
                    ]}
                    accessibilityRole="button"
                    accessibilityLabel="Share listing"
                  >
                    <Ionicons name="share-outline" size={16} color={theme.text} />
                    <Text
                      style={[
                        s.quickViewBtnSecondaryText,
                        { color: theme.text },
                      ]}
                    >
                      Share
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={onClose}
                    style={[
                      s.quickViewBtnSecondary,
                      { borderColor: theme.border },
                    ]}
                    accessibilityRole="button"
                    accessibilityLabel="Close quick view"
                  >
                    <Ionicons name="close" size={16} color={theme.muted} />
                    <Text
                      style={[
                        s.quickViewBtnSecondaryText,
                        { color: theme.muted },
                      ]}
                    >
                      Close
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            </>
          )}
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}

export const SearchResultQuickView = React.memo(SearchResultQuickViewInner);

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  quickViewOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.4)",
  },
  quickViewSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 36,
  },
  quickViewHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    alignSelf: "center",
    marginBottom: 16,
  },
  quickViewHeader: {
    flexDirection: "row",
    gap: 14,
    marginBottom: 20,
  },
  quickViewImage: {
    width: 80,
    height: 80,
    borderRadius: 10,
  },
  quickViewImagePlaceholder: {
    width: 80,
    height: 80,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  quickViewInfo: {
    flex: 1,
    gap: 2,
  },
  quickViewTitle: {
    fontSize: 16,
    fontWeight: "700",
  },
  quickViewSource: {
    fontSize: 13,
  },
  quickViewPrice: {
    fontSize: 18,
    fontWeight: "800",
    marginTop: 4,
  },
  quickViewSecondary: {
    fontSize: 12,
  },
  quickViewShipping: {
    fontSize: 12,
  },
  quickViewActions: {
    gap: 10,
  },
  quickViewBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
  },
  quickViewBtnPrimary: {
    // backgroundColor set inline
  },
  quickViewBtnPrimaryText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "700",
  },
  quickViewBtnRow: {
    flexDirection: "row",
    gap: 10,
  },
  quickViewBtnSecondary: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
  },
  quickViewBtnSecondaryText: {
    fontSize: 14,
    fontWeight: "600",
  },
});
