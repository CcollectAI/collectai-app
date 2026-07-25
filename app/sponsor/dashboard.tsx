/**
 * Sponsor Dashboard Screen — Premium Campaign Manager
 * Route: /sponsor/dashboard
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { SponsorProfileCard } from '@/components/SponsorProfileCard';
import { AnnouncementComposer } from '@/components/AnnouncementComposer';
import {
  TierPickerPanel,
  CampaignsTable,
  AnnouncementsListSection,
  EventPickerPanel,
  SponsorKpiGrid,
  SponsorQuickActions,
} from '@/components/sponsor';
import {
  ScrollView, View, Text, StyleSheet, ActivityIndicator, Animated, RefreshControl,
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

const SponsorDashboardScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();

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

  const [showCompose, setShowCompose] = useState(false);
  const [composeEventId, setComposeEventId] = useState<string | null>(null);
  const [composeTitle, setComposeTitle] = useState('');
  const [composeBody, setComposeBody] = useState('');
  const [composeSending, setComposeSending] = useState(false);

  const [editName, setEditName] = useState('');
  const [editLogoUrl, setEditLogoUrl] = useState('');
  const [editWebsiteUrl, setEditWebsiteUrl] = useState('');
  const [editContactEmail, setEditContactEmail] = useState('');
  const [editDescription, setEditDescription] = useState('');

  const { pickAndUpload, uploading: logoUploading, photoUrl: uploadedLogoUrl } = usePhotoUpload('sponsor-logo-edit');

  const handlePickEditLogo = async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const url = await pickAndUpload('gallery');
    if (url) setEditLogoUrl(url);
  };

  const stats = useMemo(() => {
    const total = sponsoredEvents.length;
    const attendees = sponsoredEvents.reduce((sum, e) => sum + (e.attendeeCount ?? e.attendeeIds?.length ?? 0), 0);
    const now = new Date();
    const active = sponsoredEvents.filter((e) => new Date(e.date) >= now && e.status !== 'cancelled').length;
    return { total, attendees, active, sent: announcements.length };
  }, [sponsoredEvents, announcements]);

  const memberSince = company?.createdAt
    ? new Date(company.createdAt).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : null;

  const eventNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of sponsoredEvents) map.set(e.id, e.title);
    return map;
  }, [sponsoredEvents]);

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

        let sponsored: CollectorsEvent[] = [];
        try {
          const events = await dataProvider.listEvents({ limit: 50 });
          sponsored = events.filter((e) => e.sponsorName === c.name || e.sponsorCompanyId === c.id);
          setSponsoredEvents(sponsored);
        } catch (e) {
          logger.error('[silent-fallback] sponsor: sponsored events load failed:', e);
          setSponsoredEvents([]);
        }

        if (sponsored.length > 0) {
          try {
            const annPromises = sponsored.slice(0, 10).map((event) =>
              dataProvider.listEventAnnouncements(event.id).catch(() => [] as EventAnnouncement[]),
            );
            const results = await Promise.all(annPromises);
            const allAnns = results.flat().sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? ''));
            setAnnouncements(allAnns.slice(0, 20));
          } catch (e) {
            logger.error('[silent-fallback] sponsor: dashboard load failed:', e);
            setAnnouncements([]);
          }
        } else { setAnnouncements([]); }
      } else { setCompany(null); }
    } catch (err: unknown) {
      logger.error('[SponsorDashboard] loadCompany error:', err);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadCompany(); }, [loadCompany]);

  useEffect(() => {
    if (!loading && company) track({ name: 'sponsor_dashboard_viewed' });
  }, [loading, company]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    await loadCompany();
    setRefreshing(false);
  }, [loadCompany, settings.hapticsEnabled]);

  const handleStartEdit = () => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); setEditing(true); };

  const handleCancelEdit = () => {
    if (company) {
      setEditName(company.name); setEditLogoUrl(company.logoUrl ?? '');
      setEditWebsiteUrl(company.websiteUrl ?? ''); setEditContactEmail(company.contactEmail);
      setEditDescription(company.description ?? '');
    }
    setEditing(false);
  };

  const handleSaveEdit = async () => {
    if (!company) return;
    if (!editName.trim() || !editContactEmail.trim()) {
      showToast({ message: 'Company name and contact email are required.', type: 'warning' }); return;
    }
    setSaving(true);
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    try {
      const updated = await dataProvider.updateSponsorCompany(company.id, {
        name: editName.trim(), contactEmail: editContactEmail.trim(),
        ...(editLogoUrl.trim() ? { logoUrl: editLogoUrl.trim() } : {}),
        ...(editWebsiteUrl.trim() ? { websiteUrl: editWebsiteUrl.trim() } : {}),
        ...(editDescription.trim() ? { description: editDescription.trim() } : {}),
      });
      setCompany(updated); setEditing(false);
      track({ name: 'sponsor_profile_updated' });
    } catch (err: unknown) {
      logger.error('[SponsorDashboard] save error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to update company. Please try again.', type: 'error' });
    } finally { setSaving(false); }
  };

  const handleCreateEvent = () => {
    if (!company) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setShowTierPicker(true);
  };

  const handleConfirmTier = async () => {
    if (!company) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    track({ name: 'sponsor_tier_selected', properties: { tier: selectedTier } });
    track({ name: 'sponsor_checkout_initiated', properties: { tier: selectedTier, company_id: company.id } });
    if (billingMode === 'monthly') {
      try {
        const { url } = await dataProvider.createSponsorSubscriptionCheckout(company.id, selectedTier);
        setShowTierPicker(false);
        if (url) { const { Linking } = require('react-native'); Linking.openURL(url); }
      } catch (err: unknown) {
        logger.error('[SponsorDashboard] subscription checkout error:', err);
        showToast({ message: (err as Error)?.message || 'Failed to start subscription checkout.', type: 'error' });
      }
    } else {
      setShowTierPicker(false);
      router.push(`/create-event?sponsorCompanyId=${company.id}&tier=${selectedTier}`);
    }
  };

  const handleAnnounce = () => {
    if (!company) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    if (sponsoredEvents.length === 0) { showToast({ message: 'Create an event first to send announcements.', type: 'info' }); return; }
    setComposeEventId(sponsoredEvents[0].id); setComposeTitle(''); setComposeBody(''); setShowCompose(true);
  };

  const handlePickEventForAnnounce = (eventId: string) => {
    setShowEventPicker(false); setComposeEventId(eventId); setComposeTitle(''); setComposeBody(''); setShowCompose(true);
  };

  const handleSendAnnouncement = async () => {
    if (!composeEventId || !composeBody.trim()) { showToast({ message: 'Please write a message.', type: 'warning' }); return; }
    setComposeSending(true);
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    try {
      const newAnn = await dataProvider.postEventAnnouncement(composeEventId, composeBody.trim(), composeTitle.trim() || undefined);
      setAnnouncements((prev) => [newAnn, ...prev]);
      setShowCompose(false); setComposeTitle(''); setComposeBody('');
      track({ name: 'sponsor_announcement_sent', properties: { event_id: composeEventId } });
      showToast({ message: 'Announcement sent to all attendees.', type: 'success' });
    } catch (err: unknown) {
      logger.error('[SponsorDashboard] send announcement error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to send announcement.', type: 'error' });
    } finally { setComposeSending(false); }
  };

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
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push('/sponsor/register'); }}
              style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Get started"
            >
              <Ionicons name="rocket-outline" size={16} color="#FFFFFF" />
              <Text style={[styles.primaryBtnText, { color: colors.accentText }]}>Get Started</Text>
            </AnimatedPressable>
          }
        />
      </View>
    );
  }

  const editLogoPreview = uploadedLogoUrl || (editLogoUrl.trim() || null);

  const kpiMetrics = [
    { label: 'Campaigns', value: stats.total, icon: 'layers-outline' as const, color: colors.accent },
    { label: 'Total Reach', value: stats.attendees, icon: 'people-outline' as const, color: colors.info },
    { label: 'Active', value: stats.active, icon: 'pulse-outline' as const, color: colors.success },
    { label: 'Sent', value: stats.sent, icon: 'paper-plane-outline' as const, color: colors.warning },
  ];

  return (
    <View style={[styles.safeArea, { backgroundColor: colors.background }]}>
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
          {/* KPI Metrics Grid */}
          <SponsorKpiGrid metrics={kpiMetrics} />

          {/* Quick Actions */}
          {!editing && !showTierPicker && !showEventPicker && (
            <SponsorQuickActions
              onCreateEvent={handleCreateEvent}
              onEditProfile={handleStartEdit}
              onAnnounce={handleAnnounce}
            />
          )}

          {showTierPicker && (
            <TierPickerPanel
              selectedTier={selectedTier}
              onSelectTier={setSelectedTier}
              billingMode={billingMode}
              onBillingModeChange={setBillingMode}
              onConfirm={handleConfirmTier}
              onCancel={() => setShowTierPicker(false)}
              hapticsEnabled={settings.hapticsEnabled}
            />
          )}

          {showEventPicker && (
            <EventPickerPanel
              events={sponsoredEvents}
              onSelect={handlePickEventForAnnounce}
              onCancel={() => setShowEventPicker(false)}
              hapticsEnabled={settings.hapticsEnabled}
            />
          )}

          <SponsorProfileCard
            company={company} memberSince={memberSince} editing={editing}
            editName={editName} onEditNameChange={setEditName}
            editContactEmail={editContactEmail} onEditContactEmailChange={setEditContactEmail}
            editLogoUrl={editLogoUrl} editWebsiteUrl={editWebsiteUrl} onEditWebsiteUrlChange={setEditWebsiteUrl}
            editDescription={editDescription} onEditDescriptionChange={setEditDescription}
            editLogoPreview={editLogoPreview} logoUploading={logoUploading} onPickEditLogo={handlePickEditLogo}
            saving={saving} onCancelEdit={handleCancelEdit} onSaveEdit={handleSaveEdit}
          />

          <CampaignsTable
            events={sponsoredEvents}
            onEventPress={(id) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push(`/events/${encodeURIComponent(id)}`); }}
            onAnnouncePress={(id) => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push(`/events/compose-announcement?eventId=${id}`); }}
            onCreateEvent={handleCreateEvent}
            hapticsEnabled={settings.hapticsEnabled}
          />

          {!!showCompose && (
            <AnnouncementComposer
              sponsoredEvents={sponsoredEvents}
              composeEventId={composeEventId} onComposeEventIdChange={setComposeEventId}
              composeTitle={composeTitle} onComposeTitleChange={setComposeTitle}
              composeBody={composeBody} onComposeBodyChange={setComposeBody}
              composeSending={composeSending} onCancel={() => setShowCompose(false)} onSend={handleSendAnnouncement}
            />
          )}

          <AnnouncementsListSection
            announcements={announcements}
            eventNameMap={eventNameMap}
            hasEvents={sponsoredEvents.length > 0}
            onAnnounce={handleAnnounce}
          />

          <View style={{ height: 40 }} />
        </Animated.View>
      </ScrollView>
      <QuickNavBar />
    </View>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { fontSize: 13 },
  titleRow: { paddingHorizontal: 16, paddingTop: 4, paddingBottom: 12 },
  headerTitle: { fontSize: 20, fontWeight: '800', letterSpacing: -0.3 },
  headerSubtitle: { fontSize: 12, marginTop: 2 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingTop: 16 },
  // kpiGrid, kpiCard, kpiIconCircle, kpiValue, kpiLabel moved to SponsorKpiGrid
  // actionsBar, actionBtn, actionBtnOutline, actionBtnPrimaryText, actionBtnSecondaryText moved to SponsorQuickActions
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10 },
  primaryBtnText: { fontSize: 13, fontWeight: '600' },
});

export default function SponsorDashboardScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sponsor Dashboard">
      <SponsorDashboardScreen />
    </ScreenErrorBoundary>
  );
}
