/**
 * CategoryCollectorSearch — inline collapsible "find collectors" dropdown that
 * drops down from the category header when "Find friends" is tapped, instead
 * of navigating away to the marketplace tab.
 *
 * Self-contained: owns its query/results state, debounces, and searches public
 * profiles via dataProvider.searchUsers. Tapping a result opens that
 * collector's profile (/users/[userId]).
 *
 * Gated by COMMUNITY_GATED at the call site (CategoryHeaderCard) — this
 * component assumes it's only mounted when community features are live.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, TextInput, StyleSheet, ActivityIndicator } from 'react-native';
import Animated, { FadeInDown, FadeOutUp } from 'react-native-reanimated';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useDebounce } from '@/hooks/useDebounce';
import { dataProvider } from '@/data';
import type { PublicUserProfile } from '@/data/types';
import type { AppTheme } from '@/hooks/useAppTheme';
import logger from '@/utils/logger';

type Props = {
  colors: AppTheme['colors'];
  onClose: () => void;
};

const CategoryCollectorSearch: React.FC<Props> = ({ colors, onClose }) => {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PublicUserProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const debounced = useDebounce(query.trim(), 350);

  useEffect(() => {
    if (!debounced) {
      setResults([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    dataProvider.searchUsers(debounced)
      .then((rows) => { if (!cancelled) setResults(rows); })
      .catch((err) => {
        logger.warn('[CategoryCollectorSearch] searchUsers error:', err);
        if (!cancelled) setResults([]);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [debounced]);

  const openProfile = useCallback((userId: string) => {
    onClose();
    router.push(`/users/${userId}`);
  }, [router, onClose]);

  return (
    <Animated.View
      entering={FadeInDown.duration(200)}
      exiting={FadeOutUp.duration(150)}
      style={styles.panel}
    >
      <View style={styles.inputRow}>
        <Ionicons name="search" size={16} color="#fff" style={styles.inputIcon} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search collectors by name or @handle"
          placeholderTextColor="rgba(255,255,255,0.7)"
          style={styles.input}
          autoFocus
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
          accessibilityLabel="Search for collectors"
        />
        <AnimatedPressable
          onPress={onClose}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Close collector search"
        >
          <Ionicons name="close" size={18} color="#fff" />
        </AnimatedPressable>
      </View>

      {debounced.length > 0 && (
        <View style={[styles.results, { backgroundColor: colors.card }]}>
          {loading ? (
            <View style={styles.stateRow}>
              <ActivityIndicator size="small" color={colors.accent} />
            </View>
          ) : results.length === 0 ? (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No collectors found
            </Text>
          ) : (
            results.map((user) => {
              const initials = (user.displayName || '?')
                .split(' ')
                .map((p) => p[0])
                .join('')
                .slice(0, 2)
                .toUpperCase() || '?';
              return (
                <AnimatedPressable
                  key={user.id}
                  style={[styles.resultRow, { borderBottomColor: colors.border }]}
                  onPress={() => openProfile(user.id)}
                  accessibilityRole="button"
                  accessibilityLabel={`View profile of ${user.displayName}`}
                >
                  <View style={[styles.avatar, { backgroundColor: colors.accent + '20' }]}>
                    <Text style={[styles.avatarText, { color: colors.accent }]}>{initials}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.resultName, { color: colors.text }]} numberOfLines={1}>
                      {user.displayName}
                    </Text>
                    {user.handle ? (
                      <Text style={[styles.resultHandle, { color: colors.muted }]} numberOfLines={1}>
                        @{user.handle}
                      </Text>
                    ) : null}
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                </AnimatedPressable>
              );
            })
          )}
        </View>
      )}
    </Animated.View>
  );
};

export default React.memo(CategoryCollectorSearch);

const styles = StyleSheet.create({
  panel: {
    marginTop: 10,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.18)',
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.5)',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  inputIcon: {
    marginRight: 6,
  },
  input: {
    flex: 1,
    color: '#fff',
    fontSize: 14,
    padding: 0,
  },
  results: {
    marginTop: 8,
    borderRadius: 12,
    overflow: 'hidden',
  },
  stateRow: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  emptyText: {
    paddingVertical: 16,
    textAlign: 'center',
    fontSize: 13,
  },
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  avatarText: {
    fontSize: 13,
    fontWeight: '700',
  },
  resultName: {
    fontSize: 14,
    fontWeight: '600',
  },
  resultHandle: {
    fontSize: 12,
    marginTop: 1,
  },
});
