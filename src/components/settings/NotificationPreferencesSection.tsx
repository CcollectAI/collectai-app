/**
 * NotificationPreferencesSection — the 8 push-notification category toggles.
 *
 * `GET`/`PUT /notifications/preferences` have always worked (all 8 keys
 * round-trip and persist — verified against prod 2026-07-30), but
 * `getNotificationPreferences` / `updateNotificationPreferences` sat on
 * `collectorsApi` with **zero screen callers**: there was no way for a user to
 * change any of them. `app/notifications.tsx` is history-only.
 *
 * That was survivable while every sending worker was disabled. It stops being
 * survivable the moment one is re-enabled — shipping pushes with no off switch
 * is the part that would be a real defect, and App Store reviewers look for it.
 *
 * Keys and their meanings are fixed by `NotificationPreferencesUpdate`
 * (server/app/features/notification_router.py:236) and enforced at delivery time
 * by `app/lib/notify.py`. Do not invent keys here — an unknown one is silently
 * dropped by Pydantic, which is exactly how a toggle becomes a no-op.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, Switch, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useToast } from '@/components/Toast';
import { collectorsApi } from '@/api/collectorsApi';
import { fireHaptic, HapticIntent } from '@/haptics';
import { logger } from '@/lib/logger';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';

/** Exactly the 8 keys the server accepts. */
type NotificationPrefs = {
  price_alerts: boolean;
  deal_alerts: boolean;
  value_changes: boolean;
  item_value_changes: boolean;
  weekly_digest: boolean;
  chat_messages: boolean;
  connection_requests: boolean;
  event_announcements: boolean;
};

/** Server defaults (notification_router.py) — all on. */
const DEFAULT_PREFS: NotificationPrefs = {
  price_alerts: true,
  deal_alerts: true,
  value_changes: true,
  item_value_changes: true,
  weekly_digest: true,
  chat_messages: true,
  connection_requests: true,
  event_announcements: true,
};

const TOGGLE_ITEMS: { key: keyof NotificationPrefs; label: string; hint: string }[] = [
  { key: 'price_alerts', label: 'Price alerts', hint: 'When an item hits your target price or moves sharply' },
  // Label only. `deal_alerts` is the STORED preference key and the `category`
  // deal_discovery_worker passes to notify_user — renaming it would orphan
  // every existing preference row, the same reason Target Hit's stored
  // notification type is still `watchlist_snipe`.
  // The hint used to name the Smart Deal Agent, which is a different product
  // (purchase mandates). This toggle governs `_check_watchlist_snipes`, whose
  // push already ships with the title "Target hit".
  { key: 'deal_alerts', label: 'Target Hit', hint: 'When a watched item is listed for sale below your target price' },
  { key: 'value_changes', label: 'Portfolio value', hint: 'Summaries when your collection value moves' },
  { key: 'item_value_changes', label: 'Item value changes', hint: 'When a single item you own changes in value' },
  { key: 'weekly_digest', label: 'Weekly digest', hint: 'One summary of your collection each week' },
  { key: 'chat_messages', label: 'Messages', hint: 'New direct messages from other collectors' },
  { key: 'connection_requests', label: 'Connection requests', hint: 'When someone asks to connect with you' },
  { key: 'event_announcements', label: 'Event announcements', hint: 'Updates from events you have RSVP\'d to' },
];

function NotificationPreferencesSectionInner() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const [prefs, setPrefs] = useState<NotificationPrefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await collectorsApi.getNotificationPreferences() as
          { preferences?: Partial<NotificationPrefs> } | undefined;
        if (cancelled) return;
        // Merge over defaults: the server may add a key before this screen knows
        // about it, and a missing key must not read as `false` (that would show
        // a category as off while pushes still arrive).
        if (res?.preferences) setPrefs({ ...DEFAULT_PREFS, ...res.preferences });
      } catch (e) {
        if (!cancelled) logger.error('[Settings] Failed to load notification preferences:', e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const updatePref = useCallback(async (key: keyof NotificationPrefs, value: boolean) => {
    const previous = prefs;
    setPrefs({ ...prefs, [key]: value });   // optimistic
    setSaving(true);
    try {
      // PUT is a partial update server-side; send only what changed.
      await collectorsApi.updateNotificationPreferences({ [key]: value });
    } catch (e) {
      // httpClient throws on a non-2xx, so this actually fires — the settings
      // writes that used a raw fetch did not, and diverged silently.
      logger.error('[Settings] Failed to save notification preference:', e);
      setPrefs(previous);
      showToast({
        message: (e as Error)?.message || 'Could not save that notification setting',
        type: 'error',
      });
    } finally {
      setSaving(false);
    }
  }, [prefs, showToast]);

  return (
    <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.sectionHeader}>
        <Ionicons name="notifications-outline" size={18} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Notifications</Text>
        {saving && <ActivityIndicator size="small" color={colors.accent} style={{ marginLeft: 8 }} />}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading settings...</Text>
        </View>
      ) : (
        TOGGLE_ITEMS.map((item, idx) => (
          <React.Fragment key={item.key}>
            {idx > 0 && <View style={[styles.divider, { backgroundColor: colors.border }]} />}
            <View style={styles.settingRow}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>{item.label}</Text>
                <Text style={[styles.settingHint, { color: colors.muted }]}>{item.hint}</Text>
              </View>
              <Switch
                value={prefs[item.key]}
                onValueChange={(v) => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  updatePref(item.key, v);
                }}
                trackColor={{ false: colors.border, true: colors.accent }}
                thumbColor={colors.accentText}
                accessibilityLabel={item.label}
              />
            </View>
          </React.Fragment>
        ))
      )}
    </View>
  );
}

export const NotificationPreferencesSection = React.memo(NotificationPreferencesSectionInner);

const styles = StyleSheet.create({
  section: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  settingInfo: {
    flex: 1,
    marginRight: 16,
  },
  settingLabel: {
    fontSize: textToken.lg,
    fontWeight: fw.medium,
  },
  settingHint: {
    fontSize: textToken.sm,
    marginTop: 2,
  },
  divider: {
    height: 1,
    marginVertical: 8,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    gap: 8,
  },
  loadingText: {
    fontSize: textToken.md,
  },
});
