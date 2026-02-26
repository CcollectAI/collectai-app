/**
 * Event Announcements Screen
 * Route: /events/[eventId]/announcements
 *
 * Lists announcements for an event. Auto-marks items as read when they
 * become visible. Host users see a compose FAB.
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  ViewToken,
  Animated,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import type { EventAnnouncement, CollectorsEvent } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';

/* -------------------------------------------------------------------------- */
/*  Helper: format timestamp                                                    */
/* -------------------------------------------------------------------------- */

function formatTimestamp(iso?: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '';
  }
}

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

const EventAnnouncementsScreen: React.FC = () => {
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  /* ---- state ---- */
  const [loading, setLoading] = useState(true);
  const [announcements, setAnnouncements] = useState<EventAnnouncement[]>([]);
  const [event, setEvent] = useState<CollectorsEvent | null>(null);
  const markedReadRef = useRef<Set<string>>(new Set());

  /* ---- load data ---- */
  const loadData = useCallback(async () => {
    if (!eventId) return;
    setLoading(true);
    try {
      const [announcementList, eventData] = await Promise.all([
        dataProvider.listEventAnnouncements(eventId),
        dataProvider.getEventById(eventId),
      ]);
      setAnnouncements(announcementList);
      setEvent(eventData);
    } catch (err: unknown) {
      logger.warn('[EventAnnouncements] loadData error:', err);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /* ---- determine if current user is host ---- */
  const [myProfile, setMyProfile] = useState<{ id: string } | null>(null);

  useEffect(() => {
    dataProvider.getMyProfile()
      .then((p) => setMyProfile(p ? { id: p.id } : null))
      .catch(() => setMyProfile(null));
  }, []);

  const isHost = useMemo(
    () => !!(myProfile && event?.hostUserId && myProfile.id === event.hostUserId),
    [myProfile, event?.hostUserId],
  );

  /* ---- auto-mark as read on viewable items change ---- */
  const handleViewableItemsChanged = useCallback(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      if (!eventId) return;
      for (const vt of viewableItems) {
        const item = vt.item as EventAnnouncement;
        if (item && !item.isRead && !markedReadRef.current.has(item.id)) {
          markedReadRef.current.add(item.id);
          dataProvider.markAnnouncementRead(eventId, item.id).catch((err) => {
            logger.warn('[EventAnnouncements] markRead error:', err);
          });
          // Optimistically update local state
          setAnnouncements((prev) =>
            prev.map((a) => (a.id === item.id ? { ...a, isRead: true } : a)),
          );
        }
      }
    },
    [eventId],
  );

  const viewabilityConfig = useRef({ itemVisiblePercentThreshold: 50 }).current;

  /* ---- navigate to compose ---- */
  const handleCompose = () => {
    if (!eventId) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(`/events/compose-announcement?eventId=${eventId}`);
  };

  /* ---- render announcement card ---- */
  const renderAnnouncement = useCallback(
    ({ item }: { item: EventAnnouncement }) => (
      <View style={[styles.announcementCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Unread indicator */}
        {!item.isRead && (
          <View style={[styles.unreadDot, { backgroundColor: colors.accent }]} />
        )}

        {/* Title */}
        {item.title && (
          <Text style={[styles.announcementTitle, { color: colors.text }]}>
            {item.title}
          </Text>
        )}

        {/* Body */}
        <Text style={[styles.announcementBody, { color: colors.text }]}>
          {item.body}
        </Text>

        {/* Image */}
        {item.imageUrl && (
          <Image
            source={{ uri: item.imageUrl }}
            style={styles.announcementImage}
            accessibilityLabel="Announcement image"
          />
        )}

        {/* Footer: timestamp + author */}
        <View style={styles.announcementFooter}>
          <Text style={[styles.footerText, { color: colors.muted }]}>
            {formatTimestamp(item.createdAt)}
          </Text>
          {item.authorUserId && (
            <View style={styles.authorRow}>
              <Ionicons name="person-outline" size={12} color={colors.muted} />
              <Text style={[styles.footerText, { color: colors.muted }]}>
                {item.authorUserId === myProfile?.id ? 'You' : 'Host'}
              </Text>
            </View>
          )}
        </View>
      </View>
    ),
    [colors, myProfile],
  );

  const keyExtractor = useCallback((item: EventAnnouncement) => item.id, []);

  /* ======================================================================== */
  /*  Render                                                                   */
  /* ======================================================================== */

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <AnimatedPressable
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.back(); }}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Announcements</Text>
        <View style={{ width: 32 }} />
      </View>

      {/* Loading */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : announcements.length === 0 ? (
        /* Empty state */
        <Animated.View style={[styles.emptyContainer, settings.animationsEnabled ? animatedStyle : undefined]}>
          <Ionicons name="megaphone-outline" size={48} color={colors.muted} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>No announcements yet</Text>
          <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
            {isHost
              ? 'Tap the compose button below to send the first announcement to attendees.'
              : 'The event host hasn\'t posted any announcements yet. Check back later.'}
          </Text>
        </Animated.View>
      ) : (
        /* Announcements list */
        <FlatList
          data={announcements}
          renderItem={renderAnnouncement}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          onViewableItemsChanged={handleViewableItemsChanged}
          viewabilityConfig={viewabilityConfig}
        />
      )}

      {/* Compose FAB (host only) */}
      {isHost && (
        <AnimatedPressable
          onPress={handleCompose}
          style={[styles.fab, { backgroundColor: colors.accent }]}
          accessibilityRole="button"
          accessibilityLabel="Compose announcement"
        >
          <Ionicons name="create-outline" size={24} color="#FFFFFF" />
        </AnimatedPressable>
      )}
      <QuickNavBar />
    </SafeAreaView>
  );
};

/* -------------------------------------------------------------------------- */
/*  Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 100, // space for FAB
  },

  /* Announcement card */
  announcementCard: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
    position: 'relative',
  },
  unreadDot: {
    position: 'absolute',
    top: 14,
    right: 14,
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  announcementTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 6,
    paddingRight: 20, // avoid overlap with unread dot
  },
  announcementBody: {
    fontSize: 14,
    lineHeight: 20,
  },
  announcementImage: {
    width: '100%',
    height: 180,
    borderRadius: 10,
    marginTop: 8,
  },
  announcementFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 10,
  },
  authorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  footerText: {
    fontSize: 12,
  },

  /* Empty state */
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },

  /* FAB */
  fab: {
    position: 'absolute',
    bottom: 32,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
});

export default function EventAnnouncementsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Announcements">
      <EventAnnouncementsScreen />
    </ScreenErrorBoundary>
  );
}
