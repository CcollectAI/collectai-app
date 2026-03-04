/**
 * Sponsor Dashboard Screen — Premium Campaign Manager
 * Route: /sponsor/dashboard
 *
 * Enterprise-grade KPI metrics, campaign management table, inline
 * announcement composer, and company profile management.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { SponsorProfileCard } from '@/components/SponsorProfileCard';
import { AnnouncementComposer } from '@/components/AnnouncementComposer';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Image,
  Animated,
  RefreshControl,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { dataProvider } from '@/data';
import type { SponsorCompany, CollectorsEvent, SponsorTier, EventAnnouncement } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';
import { useToast } from '@/components/Toast';
import { EmptyState } from '@/components/EmptyState';
import { usePhotoUpload } from '@/hooks/usePhotoUpload';
import { track } from '@/analytics/track';

/* -------------------------------------------------------------------------- */
/*  Helpers & constants                                                        */
/* -------------------------------------------------------------------------- */

function getEventStatus(event: CollectorsEvent): { label: string; color: string; icon: keyof typeof Ionicons.glyphMap } {
  if (event.status === 'cancelled') return { label: 'Cancelled', color: '#EF4444', icon: 'close-circle' };
  if (event.status === 'draft') return { label: 'Draft', color: '#F59E0B', icon: 'create-outline' };
  const eventDate = new Date(event.date);
  const now = new Date();
  if (eventDate < now) return { label: 'Past', color: '#94A3B8', icon: 'time-outline' };
  return { label: 'Upcoming', color: '#10B981', icon: 'calendar-outline' };
}

function formatRelativeDate(dateStr?: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const TIERS: { id: SponsorTier; name: string; badge?: string; features: string[] }[] = [
  {
    id: 'featured',
    name: 'Featured',
    features: ['Event listing', 'Category placement', 'Basic analytics'],
  },
  {
    id: 'promoted',
    name: 'Promoted',
    badge: 'POPULAR',
    features: ['Everything in Featured', 'Homepage banner', 'Push notifications', 'Priority support'],
  },
  {
    id: 'spotlight',
    name: 'Spotlight',
    features: ['Everything in Promoted', 'Dedicated landing page', 'Custom branding', 'Advanced analytics'],
  },
];

const SHADOW_SM = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 3 },
  android: { elevation: 1 },
  default: {},
}) as Record<string, unknown>;

const SHADOW_MD = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 8 },
  android: { elevation: 3 },
  default: {},
}) as Record<string, unknown>;

const SHADOW_LG = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.1, shadowRadius: 12 },
  android: { elevation: 5 },
  default: {},
}) as Record<string, unknown>;

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

const SponsorDashboardScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();

  /* ---- state ---- */
  const [loading, setLoading] = useState(true);
  const [company, setCompany] = useState<SponsorCompany | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sponsoredEvents, setSponsoredEvents] = useState<CollectorsEvent[]>([]);
  const [announcements, setAnnouncements] = useState<EventAnnouncement[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [showTierPicker, setShowTierPicker] = useState(false);
  const [selectedTier, setSelectedTier] = useState<SponsorTier>('featured');
  const [billingMode, setBillingMode] = useState<'per_event' | 'monthly'>('per_event');
  const [showEventPicker, setShowEventPicker] = useState(false);

  /* ---- inline compose state ---- */
  const [showCompose, setShowCompose] = useState(false);
  const [composeEventId, setComposeEventId] = useState<string | null>(null);
  const [composeTitle, setComposeTitle] = useState('');
  const [composeBody, setComposeBody] = useState('');
  const [composeSending, setComposeSending] = useState(false);

  /* ---- editable fields ---- */
  const [editName, setEditName] = useState('');
  const [editLogoUrl, setEditLogoUrl] = useState('');
  const [editWebsiteUrl, setEditWebsiteUrl] = useState('');
  const [editContactEmail, setEditContactEmail] = useState('');
  const [editDescription, setEditDescription] = useState('');

  /* ---- photo upload for logo (edit mode) ---- */
  const { pickAndUpload, uploading: logoUploading, photoUrl: uploadedLogoUrl } = usePhotoUpload('sponsor-logo-edit');

  const handlePickEditLogo = async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const url = await pickAndUpload('gallery');
    if (url) {
      setEditLogoUrl(url);
    }
  };

  /* ---- computed ---- */
  const stats = useMemo(() => {
    const total = sponsoredEvents.length;
    const attendees = sponsoredEvents.reduce(
      (sum, e) => sum + (e.attendeeCount ?? e.attendeeIds?.length ?? 0),
      0,
    );
    const now = new Date();
    const active = sponsoredEvents.filter(
      (e) => new Date(e.date) >= now && e.status !== 'cancelled',
    ).length;
    return { total, attendees, active, sent: announcements.length };
  }, [sponsoredEvents, announcements]);

  const memberSince = company?.createdAt
    ? new Date(company.createdAt).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : null;

  const eventNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of sponsoredEvents) {
      map.set(e.id, e.title);
    }
    return map;
  }, [sponsoredEvents]);

  /* ---- load company ---- */
  const loadCompany = useCallback(async () => {
    setLoading(true);
    try {
      const companies = await dataProvider.getMySponsorCompanies();
      if (companies.length > 0) {
        const c = companies[0];
        setCompany(c);
        setEditName(c.name);
        setEditLogoUrl(c.logoUrl ?? '');
        setEditWebsiteUrl(c.websiteUrl ?? '');
        setEditContactEmail(c.contactEmail);
        setEditDescription(c.description ?? '');

        // Load sponsored events
        let sponsored: CollectorsEvent[] = [];
        try {
          const events = await dataProvider.listEvents({ limit: 50 });
          sponsored = events.filter(
            (e) => e.sponsorName === c.name || e.sponsorCompanyId === c.id,
          );
          setSponsoredEvents(sponsored);
        } catch {
          setSponsoredEvents([]);
        }

        // Load announcements for all sponsored events (parallel)
        if (sponsored.length > 0) {
          try {
            const annPromises = sponsored.slice(0, 10).map((event) =>
              dataProvider.listEventAnnouncements(event.id).catch(() => [] as EventAnnouncement[]),
            );
            const results = await Promise.all(annPromises);
            const allAnns = results
              .flat()
              .sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? ''));
            setAnnouncements(allAnns.slice(0, 20));
          } catch {
            setAnnouncements([]);
          }
        } else {
          setAnnouncements([]);
        }
      } else {
        setCompany(null);
      }
    } catch (err: unknown) {
      logger.warn('[SponsorDashboard] loadCompany error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCompany();
  }, [loadCompany]);

  // Track dashboard view once loading finishes and company exists
  useEffect(() => {
    if (!loading && company) {
      track({ name: 'sponsor_dashboard_viewed' });
    }
  }, [loading, company]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    await loadCompany();
    setRefreshing(false);
  }, [loadCompany, settings.hapticsEnabled]);

  /* ---- enter edit mode ---- */
  const handleStartEdit = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setEditing(true);
  };

  /* ---- cancel edit ---- */
  const handleCancelEdit = () => {
    if (company) {
      setEditName(company.name);
      setEditLogoUrl(company.logoUrl ?? '');
      setEditWebsiteUrl(company.websiteUrl ?? '');
      setEditContactEmail(company.contactEmail);
      setEditDescription(company.description ?? '');
    }
    setEditing(false);
  };

  /* ---- save edits ---- */
  const handleSaveEdit = async () => {
    if (!company) return;
    if (!editName.trim() || !editContactEmail.trim()) {
      showToast({ message: 'Company name and contact email are required.', type: 'warning' });
      return;
    }

    setSaving(true);
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    try {
      const updated = await dataProvider.updateSponsorCompany(company.id, {
        name: editName.trim(),
        contactEmail: editContactEmail.trim(),
        ...(editLogoUrl.trim() ? { logoUrl: editLogoUrl.trim() } : {}),
        ...(editWebsiteUrl.trim() ? { websiteUrl: editWebsiteUrl.trim() } : {}),
        ...(editDescription.trim() ? { description: editDescription.trim() } : {}),
      });
      setCompany(updated);
      setEditing(false);
      track({ name: 'sponsor_profile_updated' });
    } catch (err: unknown) {
      logger.warn('[SponsorDashboard] save error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to update company. Please try again.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  /* ---- create sponsored event (opens tier picker) ---- */
  const handleCreateEvent = () => {
    if (!company) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setShowTierPicker(true);
  };

  /* ---- confirm tier and navigate ---- */
  const handleConfirmTier = async () => {
    if (!company) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    track({ name: 'sponsor_tier_selected', properties: { tier: selectedTier } });
    track({ name: 'sponsor_checkout_initiated', properties: { tier: selectedTier, company_id: company.id } });

    if (billingMode === 'monthly') {
      // Monthly subscription — open Stripe checkout
      try {
        const { url } = await dataProvider.createSponsorSubscriptionCheckout(company.id, selectedTier);
        setShowTierPicker(false);
        if (url) {
          const { Linking } = require('react-native');
          Linking.openURL(url);
        }
      } catch (err: unknown) {
        logger.warn('[SponsorDashboard] subscription checkout error:', err);
        showToast({ message: (err as Error)?.message || 'Failed to start subscription checkout.', type: 'error' });
      }
    } else {
      // Per-event — navigate to create event
      setShowTierPicker(false);
      router.push(`/create-event?sponsorCompanyId=${company.id}&tier=${selectedTier}`);
    }
  };

  /* ---- announce action (opens inline compose) ---- */
  const handleAnnounce = () => {
    if (!company) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    if (sponsoredEvents.length === 0) {
      showToast({ message: 'Create an event first to send announcements.', type: 'info' });
      return;
    }
    setComposeEventId(sponsoredEvents[0].id);
    setComposeTitle('');
    setComposeBody('');
    setShowCompose(true);
  };

  const handlePickEventForAnnounce = (eventId: string) => {
    setShowEventPicker(false);
    setComposeEventId(eventId);
    setComposeTitle('');
    setComposeBody('');
    setShowCompose(true);
  };

  const handleSendAnnouncement = async () => {
    if (!composeEventId || !composeBody.trim()) {
      showToast({ message: 'Please write a message.', type: 'warning' });
      return;
    }

    setComposeSending(true);
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    try {
      const newAnn = await dataProvider.postEventAnnouncement(
        composeEventId,
        composeBody.trim(),
        composeTitle.trim() || undefined,
      );
      setAnnouncements((prev) => [newAnn, ...prev]);
      setShowCompose(false);
      setComposeTitle('');
      setComposeBody('');
      track({ name: 'sponsor_announcement_sent', properties: { event_id: composeEventId } });
      showToast({ message: 'Announcement sent to all attendees.', type: 'success' });
    } catch (err: unknown) {
      logger.warn('[SponsorDashboard] send announcement error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to send announcement.', type: 'error' });
    } finally {
      setComposeSending(false);
    }
  };

  /* ======================================================================== */
  /*  Loading state                                                            */
  /* ======================================================================== */

  if (loading) {
    return (
      <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading dashboard...</Text>
        </View>
      </View>
    );
  }

  /* ======================================================================== */
  /*  No company — registration CTA                                            */
  /* ======================================================================== */

  if (!company) {
    return (
      <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <EmptyState
          icon="megaphone-outline"
          title="Start Sponsoring Events"
          subtitle="Register your company to create sponsored events and reach thousands of passionate collectors."
          colors={colors}
          action={
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push('/sponsor/register');
              }}
              style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Get started"
            >
              <Ionicons name="rocket-outline" size={16} color="#FFFFFF" />
              <Text style={styles.primaryBtnText}>Get Started</Text>
            </AnimatedPressable>
          }
        />
      </View>
    );
  }

  /* ======================================================================== */
  /*  Dashboard with company                                                   */
  /* ======================================================================== */

  const editLogoPreview = uploadedLogoUrl || (editLogoUrl.trim() || null);

  const kpiMetrics = [
    { label: 'Campaigns', value: stats.total, icon: 'layers-outline' as const, color: colors.accent },
    { label: 'Total Reach', value: stats.attendees, icon: 'people-outline' as const, color: '#6366F1' },
    { label: 'Active', value: stats.active, icon: 'pulse-outline' as const, color: '#10B981' },
    { label: 'Sent', value: stats.sent, icon: 'paper-plane-outline' as const, color: '#F59E0B' },
  ];

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
      {/* Title */}
      <View style={[styles.titleRow, { backgroundColor: colors.background }]}>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Campaign Manager</Text>
        <Text style={[styles.headerSubtitle, { color: colors.muted }]} numberOfLines={1}>{company.name}</Text>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
          {/* ============================================================ */}
          {/*  KPI Metrics Grid                                            */}
          {/* ============================================================ */}
          <View style={styles.kpiGrid}>
            {kpiMetrics.map((metric) => (
              <View
                key={metric.label}
                style={[styles.kpiCard, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_SM]}
              >
                <View style={[styles.kpiIconCircle, { backgroundColor: metric.color + '12' }]}>
                  <Ionicons name={metric.icon} size={16} color={metric.color} />
                </View>
                <Text style={[styles.kpiValue, { color: colors.text }]}>{metric.value}</Text>
                <Text style={[styles.kpiLabel, { color: colors.muted }]}>{metric.label}</Text>
              </View>
            ))}
          </View>

          {/* ============================================================ */}
          {/*  Quick Actions Bar                                           */}
          {/* ============================================================ */}
          {!editing && !showTierPicker && !showEventPicker && (
            <View style={[styles.actionsBar, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_SM]}>
              <AnimatedPressable
                onPress={handleCreateEvent}
                style={[styles.actionBtn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="New campaign"
              >
                <Ionicons name="add" size={15} color="#FFFFFF" />
                <Text style={styles.actionBtnPrimaryText}>New Campaign</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={handleStartEdit}
                style={[styles.actionBtn, styles.actionBtnOutline, { borderColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel="Edit profile"
              >
                <Ionicons name="create-outline" size={14} color={colors.text} />
                <Text style={[styles.actionBtnSecondaryText, { color: colors.text }]}>Edit Profile</Text>
              </AnimatedPressable>
              <AnimatedPressable
                onPress={handleAnnounce}
                style={[styles.actionBtn, styles.actionBtnOutline, { borderColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel="Send announcement"
              >
                <Ionicons name="megaphone-outline" size={14} color={colors.text} />
                <Text style={[styles.actionBtnSecondaryText, { color: colors.text }]}>Announce</Text>
              </AnimatedPressable>
            </View>
          )}

          {/* ============================================================ */}
          {/*  Tier Picker (shown when creating event)                      */}
          {/* ============================================================ */}
          {showTierPicker && (
            <View style={[styles.pickerContainer, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_MD]}>
              <View style={styles.pickerHeader}>
                <View style={[styles.pickerIconCircle, { backgroundColor: colors.accent + '12' }]}>
                  <Ionicons name="ribbon-outline" size={16} color={colors.accent} />
                </View>
                <View>
                  <Text style={[styles.pickerTitle, { color: colors.text }]}>Select Sponsorship Tier</Text>
                  <Text style={[styles.pickerSubtitle, { color: colors.muted }]}>Choose the visibility level for your event</Text>
                </View>
              </View>

              <View style={[styles.pickerDivider, { backgroundColor: colors.border }]} />

              {TIERS.map((tier, i) => (
                <AnimatedPressable
                  key={tier.id}
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    setSelectedTier(tier.id);
                  }}
                  style={[
                    styles.tierCard,
                    { backgroundColor: selectedTier === tier.id ? colors.accent + '06' : 'transparent', borderColor: selectedTier === tier.id ? colors.accent : colors.border },
                    selectedTier === tier.id && { borderWidth: 2 },
                    i < TIERS.length - 1 && { marginBottom: 8 },
                  ]}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: selectedTier === tier.id }}
                  accessibilityLabel={`${tier.name} tier`}
                >
                  <View style={styles.tierCardRow}>
                    <View
                      style={[
                        styles.radioOuter,
                        { borderColor: selectedTier === tier.id ? colors.accent : colors.muted },
                      ]}
                    >
                      {selectedTier === tier.id && (
                        <View style={[styles.radioInner, { backgroundColor: colors.accent }]} />
                      )}
                    </View>
                    <View style={styles.tierCardInfo}>
                      <View style={styles.tierNameRow}>
                        <Text style={[styles.tierName, { color: colors.text }]}>{tier.name}</Text>
                        {tier.badge && (
                          <View style={[styles.popularBadge, { backgroundColor: colors.accent }]}>
                            <Text style={styles.popularBadgeText}>{tier.badge}</Text>
                          </View>
                        )}
                      </View>
                      {tier.features.map((f) => (
                        <View key={f} style={styles.featureRow}>
                          <Ionicons name="checkmark" size={13} color={colors.accent} />
                          <Text style={[styles.featureText, { color: colors.muted }]}>{f}</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                </AnimatedPressable>
              ))}

              {/* Billing mode toggle */}
              <View style={styles.billingModeRow}>
                <AnimatedPressable
                  onPress={() => setBillingMode('per_event')}
                  style={[
                    styles.billingModeBtn,
                    {
                      backgroundColor: billingMode === 'per_event' ? colors.accent : colors.background,
                      borderColor: billingMode === 'per_event' ? colors.accent : colors.border,
                    },
                  ]}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: billingMode === 'per_event' }}
                >
                  <Text style={{ fontSize: 13, fontWeight: '600', color: billingMode === 'per_event' ? '#FFF' : colors.text }}>
                    Per Event
                  </Text>
                </AnimatedPressable>
                <AnimatedPressable
                  onPress={() => setBillingMode('monthly')}
                  style={[
                    styles.billingModeBtn,
                    {
                      backgroundColor: billingMode === 'monthly' ? colors.accent : colors.background,
                      borderColor: billingMode === 'monthly' ? colors.accent : colors.border,
                    },
                  ]}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: billingMode === 'monthly' }}
                >
                  <Text style={{ fontSize: 13, fontWeight: '600', color: billingMode === 'monthly' ? '#FFF' : colors.text }}>
                    Monthly
                  </Text>
                </AnimatedPressable>
              </View>

              <View style={[styles.pickerDivider, { backgroundColor: colors.border }]} />

              <View style={styles.pickerFooter}>
                <AnimatedPressable
                  onPress={() => setShowTierPicker(false)}
                  style={[styles.outlineBtn, { borderColor: colors.border }]}
                  accessibilityRole="button"
                  accessibilityLabel="Cancel"
                >
                  <Text style={[styles.outlineBtnText, { color: colors.muted }]}>Cancel</Text>
                </AnimatedPressable>
                <AnimatedPressable
                  onPress={handleConfirmTier}
                  style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Continue"
                >
                  <Text style={styles.primaryBtnText}>
                    {billingMode === 'monthly' ? 'Subscribe' : 'Continue'}
                  </Text>
                  <Ionicons name="arrow-forward" size={15} color="#FFFFFF" />
                </AnimatedPressable>
              </View>
            </View>
          )}

          {/* ============================================================ */}
          {/*  Event Picker (shown when announcing to multiple events)       */}
          {/* ============================================================ */}
          {showEventPicker && (
            <View style={[styles.pickerContainer, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_MD]}>
              <View style={styles.pickerHeader}>
                <View style={[styles.pickerIconCircle, { backgroundColor: colors.accent + '12' }]}>
                  <Ionicons name="megaphone-outline" size={16} color={colors.accent} />
                </View>
                <View>
                  <Text style={[styles.pickerTitle, { color: colors.text }]}>Send Announcement</Text>
                  <Text style={[styles.pickerSubtitle, { color: colors.muted }]}>Select which event to notify</Text>
                </View>
              </View>

              <View style={[styles.pickerDivider, { backgroundColor: colors.border }]} />

              {sponsoredEvents.map((event) => {
                const status = getEventStatus(event);
                return (
                  <AnimatedPressable
                    key={event.id}
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      handlePickEventForAnnounce(event.id);
                    }}
                    style={[styles.eventPickerRow, { borderColor: colors.border }]}
                    accessibilityRole="button"
                    accessibilityLabel={`Announce to ${event.title}`}
                  >
                    <View style={[styles.statusIndicator, { backgroundColor: status.color }]} />
                    <View style={styles.eventPickerInfo}>
                      <Text style={[styles.eventPickerName, { color: colors.text }]} numberOfLines={1}>{event.title}</Text>
                      <Text style={[styles.eventPickerMeta, { color: colors.muted }]}>
                        {event.date} · {event.attendeeCount ?? event.attendeeIds?.length ?? 0} attendees
                      </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                  </AnimatedPressable>
                );
              })}

              <View style={[styles.pickerDivider, { backgroundColor: colors.border }]} />

              <AnimatedPressable
                onPress={() => setShowEventPicker(false)}
                style={[styles.outlineBtn, { borderColor: colors.border, alignSelf: 'stretch' }]}
                accessibilityRole="button"
                accessibilityLabel="Cancel"
              >
                <Text style={[styles.outlineBtnText, { color: colors.muted }]}>Cancel</Text>
              </AnimatedPressable>
            </View>
          )}

          {/* ============================================================ */}
          {/*  Company Profile                                              */}
          {/* ============================================================ */}
          <SponsorProfileCard
            company={company}
            colors={colors}
            memberSince={memberSince}
            editing={editing}
            editName={editName}
            onEditNameChange={setEditName}
            editContactEmail={editContactEmail}
            onEditContactEmailChange={setEditContactEmail}
            editLogoUrl={editLogoUrl}
            editWebsiteUrl={editWebsiteUrl}
            onEditWebsiteUrlChange={setEditWebsiteUrl}
            editDescription={editDescription}
            onEditDescriptionChange={setEditDescription}
            editLogoPreview={editLogoPreview}
            logoUploading={logoUploading}
            onPickEditLogo={handlePickEditLogo}
            saving={saving}
            onCancelEdit={handleCancelEdit}
            onSaveEdit={handleSaveEdit}
          />

          {/* ============================================================ */}
          {/*  Campaigns Table                                              */}
          {/* ============================================================ */}
          <View style={styles.sectionWrap}>
            <View style={styles.sectionLabelRow}>
              <Text style={[styles.sectionLabel, { color: colors.muted }]}>CAMPAIGNS</Text>
              {sponsoredEvents.length > 0 && (
                <View style={[styles.countBadge, { backgroundColor: colors.accent + '15' }]}>
                  <Text style={[styles.countBadgeText, { color: colors.accent }]}>{sponsoredEvents.length}</Text>
                </View>
              )}
            </View>

            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border, padding: 0, overflow: 'hidden' }, SHADOW_SM]}>
              {/* Table header */}
              {sponsoredEvents.length > 0 && (
                <View style={[styles.tableHead, { backgroundColor: colors.background, borderBottomColor: colors.border }]}>
                  <Text style={[styles.tableHeadCell, styles.colStatus, { color: colors.muted }]}>Status</Text>
                  <Text style={[styles.tableHeadCell, styles.colCampaign, { color: colors.muted }]}>Campaign</Text>
                  <Text style={[styles.tableHeadCell, styles.colReach, { color: colors.muted }]}>Reach</Text>
                  <View style={styles.colActions} />
                </View>
              )}

              {sponsoredEvents.length > 0 ? (
                sponsoredEvents.map((event, idx) => {
                  const status = getEventStatus(event);
                  const reach = event.attendeeCount ?? event.attendeeIds?.length ?? 0;
                  const isLast = idx === sponsoredEvents.length - 1;
                  return (
                    <AnimatedPressable
                      key={event.id}
                      style={[styles.tableRow, !isLast && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }]}
                      onPress={() => {
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                        router.push(`/events/${encodeURIComponent(event.id)}`);
                      }}
                      accessibilityRole="button"
                      accessibilityLabel={`${event.title}, ${status.label}, ${reach} attendees`}
                    >
                      <View style={styles.colStatus}>
                        <View style={[styles.statusPill, { backgroundColor: status.color + '18' }]}>
                          <View style={[styles.statusDot, { backgroundColor: status.color }]} />
                          <Text style={[styles.statusText, { color: status.color }]}>{status.label}</Text>
                        </View>
                      </View>

                      <View style={styles.colCampaign}>
                        <Text style={[styles.campaignName, { color: colors.text }]} numberOfLines={1}>
                          {event.title}
                        </Text>
                        <View style={styles.campaignMeta}>
                          <Text style={[styles.campaignMetaText, { color: colors.muted }]}>
                            {event.kind.replace('_', ' ')} · {event.date}
                          </Text>
                          {event.sponsorTier && (
                            <View style={[styles.tierChip, { backgroundColor: colors.accent + '12' }]}>
                              <Text style={[styles.tierChipText, { color: colors.accent }]}>
                                {event.sponsorTier.charAt(0).toUpperCase() + event.sponsorTier.slice(1)}
                              </Text>
                            </View>
                          )}
                        </View>
                      </View>

                      <View style={styles.colReach}>
                        <Text style={[styles.reachValue, { color: colors.text }]}>{reach}</Text>
                      </View>

                      <View style={styles.colActions}>
                        <AnimatedPressable
                          onPress={(e) => {
                            e.stopPropagation?.();
                            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                            router.push(`/events/compose-announcement?eventId=${event.id}`);
                          }}
                          style={[styles.iconBtn, { backgroundColor: colors.accent + '10' }]}
                          accessibilityRole="button"
                          accessibilityLabel={`Announce to ${event.title}`}
                        >
                          <Ionicons name="megaphone-outline" size={13} color={colors.accent} />
                        </AnimatedPressable>
                        <Ionicons name="chevron-forward" size={14} color={colors.muted} />
                      </View>
                    </AnimatedPressable>
                  );
                })
              ) : (
                <View style={{ padding: 20 }}>
                  <EmptyState
                    icon="layers-outline"
                    title="No Campaigns Yet"
                    subtitle="Create your first sponsored event to start reaching collectors."
                    colors={colors}
                    style={{ paddingVertical: 16 }}
                    action={
                      <AnimatedPressable
                        onPress={handleCreateEvent}
                        style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
                        accessibilityRole="button"
                        accessibilityLabel="Create your first event"
                      >
                        <Ionicons name="add" size={16} color="#FFFFFF" />
                        <Text style={styles.primaryBtnText}>New Campaign</Text>
                      </AnimatedPressable>
                    }
                  />
                </View>
              )}
            </View>
          </View>

          {/* ============================================================ */}
          {/*  Announcements                                                */}
          {/* ============================================================ */}
          <View style={styles.sectionWrap}>
            <View style={styles.sectionLabelRow}>
              <Text style={[styles.sectionLabel, { color: colors.muted }]}>ANNOUNCEMENTS</Text>
              {announcements.length > 0 && (
                <View style={[styles.countBadge, { backgroundColor: '#F59E0B' + '15' }]}>
                  <Text style={[styles.countBadgeText, { color: '#F59E0B' }]}>{announcements.length}</Text>
                </View>
              )}
            </View>

            {/* Inline compose form */}
            {!!showCompose && (
              <AnnouncementComposer
                colors={colors}
                sponsoredEvents={sponsoredEvents}
                composeEventId={composeEventId}
                onComposeEventIdChange={setComposeEventId}
                composeTitle={composeTitle}
                onComposeTitleChange={setComposeTitle}
                composeBody={composeBody}
                onComposeBodyChange={setComposeBody}
                composeSending={composeSending}
                onCancel={() => setShowCompose(false)}
                onSend={handleSendAnnouncement}
              />
            )}

            {/* Announcements list */}
            {announcements.length > 0 ? (
              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border, padding: 0, overflow: 'hidden' }, SHADOW_SM]}>
                {announcements.slice(0, 10).map((ann, idx) => {
                  const eventTitle = eventNameMap.get(ann.eventId) || 'Event';
                  const isLast = idx === Math.min(announcements.length, 10) - 1;
                  return (
                    <View
                      key={ann.id}
                      style={[
                        styles.annRow,
                        !isLast && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
                      ]}
                    >
                      <View style={styles.annRowLeft}>
                        <View style={[styles.annIcon, { backgroundColor: '#F59E0B' + '12' }]}>
                          <Ionicons name="megaphone" size={12} color="#F59E0B" />
                        </View>
                      </View>
                      <View style={styles.annRowContent}>
                        <View style={styles.annRowHeader}>
                          <Text style={[styles.annTitle, { color: colors.text }]} numberOfLines={1}>
                            {ann.title || eventTitle}
                          </Text>
                          <Text style={[styles.annTime, { color: colors.muted }]}>
                            {formatRelativeDate(ann.createdAt)}
                          </Text>
                        </View>
                        {ann.title && (
                          <Text style={[styles.annEventName, { color: colors.muted }]}>{eventTitle}</Text>
                        )}
                        <Text style={[styles.annBody, { color: colors.text }]} numberOfLines={2}>
                          {ann.body}
                        </Text>
                        {ann.imageUrl && (
                          <Image
                            source={{ uri: ann.imageUrl }}
                            style={styles.annImage}
                            accessibilityLabel="Announcement image"
                          />
                        )}
                      </View>
                    </View>
                  );
                })}
              </View>
            ) : (
              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_SM]}>
                <View style={styles.emptyCenter}>
                  <View style={[styles.emptyIconCircle, { backgroundColor: '#F59E0B' + '10' }]}>
                    <Ionicons name="megaphone-outline" size={24} color="#F59E0B" />
                  </View>
                  <Text style={[styles.emptyTitle, { color: colors.text }]}>No Announcements Yet</Text>
                  <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
                    Notify event attendees about updates, schedule changes, or exclusive offers.
                  </Text>
                  {sponsoredEvents.length > 0 && (
                    <AnimatedPressable
                      onPress={handleAnnounce}
                      style={styles.emptyAction}
                      accessibilityRole="button"
                      accessibilityLabel="Send your first announcement"
                    >
                      <Ionicons name="megaphone-outline" size={13} color={colors.accent} />
                      <Text style={[styles.emptyActionText, { color: colors.accent }]}>Send First Announcement</Text>
                    </AnimatedPressable>
                  )}
                </View>
              </View>
            )}
          </View>

          <View style={{ height: 40 }} />
        </Animated.View>
      </ScrollView>
      <QuickNavBar />
    </View>
  );
};

/* -------------------------------------------------------------------------- */
/*  Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 13,
  },

  /* Header */
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
    width: 32,
  },
  headerCenter: {
    alignItems: 'center',
    flex: 1,
  },
  titleRow: {
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 12,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '800',
    letterSpacing: -0.3,
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },

  /* Scroll */
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
  },

  /* Shared section */
  sectionWrap: {
    marginBottom: 24,
  },
  sectionLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  countBadge: {
    paddingHorizontal: 7,
    paddingVertical: 1,
    borderRadius: 8,
    marginBottom: 10,
  },
  countBadgeText: {
    fontSize: 10,
    fontWeight: '700',
  },

  /* Card base */
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
  },

  /* KPI Grid */
  kpiGrid: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  kpiCard: {
    flex: 1,
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 14,
    paddingHorizontal: 4,
    gap: 6,
  },
  kpiIconCircle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
  kpiValue: {
    fontSize: 20,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  kpiLabel: {
    fontSize: 9,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },

  /* Quick Actions */
  actionsBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderRadius: 12,
    borderWidth: 1,
    padding: 8,
    marginBottom: 24,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  actionBtnOutline: {
    borderWidth: 1,
    backgroundColor: 'transparent',
  },
  actionBtnPrimaryText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  actionBtnSecondaryText: {
    fontSize: 12,
    fontWeight: '600',
  },

  /* Shared buttons */
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 11,
    paddingHorizontal: 18,
    borderRadius: 10,
  },
  primaryBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  outlineBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 11,
    paddingHorizontal: 18,
    borderRadius: 10,
    borderWidth: 1,
  },
  outlineBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },

  /* Tier / Event picker container */
  pickerContainer: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
    marginBottom: 24,
  },
  pickerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  pickerIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pickerTitle: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: -0.2,
  },
  pickerSubtitle: {
    fontSize: 12,
    marginTop: 1,
  },
  pickerDivider: {
    height: 1,
    marginVertical: 14,
  },
  pickerFooter: {
    flexDirection: 'row',
    gap: 10,
  },
  billingModeRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  billingModeBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },

  /* Tier cards */
  tierCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  tierCardRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  tierCardInfo: {
    flex: 1,
  },
  tierNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  tierName: {
    fontSize: 14,
    fontWeight: '700',
  },
  popularBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 5,
  },
  popularBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 2,
  },
  featureText: {
    fontSize: 12,
    flex: 1,
  },

  /* Event picker rows */
  eventPickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 10,
  },
  statusIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  eventPickerInfo: {
    flex: 1,
  },
  eventPickerName: {
    fontSize: 14,
    fontWeight: '600',
  },
  eventPickerMeta: {
    fontSize: 11,
    marginTop: 2,
  },

  /* Campaign table */
  tableHead: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
  },
  tableHeadCell: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  colStatus: {
    width: 78,
  },
  colCampaign: {
    flex: 1,
    paddingRight: 8,
  },
  colReach: {
    width: 44,
    alignItems: 'center',
  },
  colActions: {
    width: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 6,
  },

  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '600',
  },
  campaignName: {
    fontSize: 14,
    fontWeight: '600',
    letterSpacing: -0.1,
  },
  campaignMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 3,
  },
  campaignMetaText: {
    fontSize: 11,
  },
  tierChip: {
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
  },
  tierChipText: {
    fontSize: 9,
    fontWeight: '700',
  },
  reachValue: {
    fontSize: 14,
    fontWeight: '700',
  },
  iconBtn: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },

  /* Announcement rows */
  annRow: {
    flexDirection: 'row',
    padding: 14,
    gap: 10,
  },
  annRowLeft: {
    paddingTop: 2,
  },
  annIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  annRowContent: {
    flex: 1,
  },
  annRowHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  annTitle: {
    fontSize: 13,
    fontWeight: '700',
    flex: 1,
    marginRight: 8,
  },
  annTime: {
    fontSize: 10,
    fontWeight: '500',
  },
  annEventName: {
    fontSize: 11,
    marginBottom: 4,
  },
  annBody: {
    fontSize: 13,
    lineHeight: 18,
  },
  annImage: {
    width: '100%',
    height: 120,
    borderRadius: 8,
    marginTop: 8,
  },

  /* Empty state */
  emptyCenter: {
    alignItems: 'center',
    paddingVertical: 20,
    paddingHorizontal: 12,
  },
  emptyIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: -0.1,
  },
  emptySubtitle: {
    fontSize: 12,
    textAlign: 'center',
    lineHeight: 17,
    marginTop: 4,
    maxWidth: 260,
  },
  emptyAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 14,
    paddingVertical: 6,
  },
  emptyActionText: {
    fontSize: 13,
    fontWeight: '600',
  },
});

export default function SponsorDashboardScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sponsor Dashboard">
      <SponsorDashboardScreen />
    </ScreenErrorBoundary>
  );
}
