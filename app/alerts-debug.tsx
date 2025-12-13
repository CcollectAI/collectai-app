import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import {
  AlertConfig,
  getAlerts,
  upsertAlert,
  disableAlert,
} from '@/services/alertsClient';

const AlertsDebugScreen: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [collectionKey, setCollectionKey] = useState('');
  const [thresholdPct, setThresholdPct] = useState('90');

  const [category, setCategory] = useState('');
  const [rarityMinPct, setRarityMinPct] = useState('80');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAlerts();
      setAlerts(data);
    } catch (e: any) {
      console.error('[AlertsDebug] load error', e);
      setError('Could not load alerts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getAlerts();
        if (!cancelled) {
          setAlerts(data);
        }
      } catch (e: any) {
        console.error('[AlertsDebug] initial load error', e);
        if (!cancelled) {
          setError('Could not load alerts.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleCreateCompletenessAlert = async () => {
    const pct = parseFloat(thresholdPct.replace(',', '.'));
    if (!collectionKey || Number.isNaN(pct)) return;

    const alert: AlertConfig = {
      type: 'completeness',
      collection_key: collectionKey,
      threshold_pct: pct,
      enabled: true,
    };

    await upsertAlert(alert);
    await load();
  };

  const handleCreateRarityAlert = async () => {
    const pct = parseFloat(rarityMinPct.replace(',', '.'));
    if (!category || Number.isNaN(pct)) return;

    const alert: AlertConfig = {
      type: 'rarity',
      category,
      rarity_min_pct: pct,
      enabled: true,
    };

    await upsertAlert(alert);
    await load();
  };

  const handleDisable = async (id?: string) => {
    if (!id) return;
    await disableAlert(id);
    await load();
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Alerts debug</Text>
        <Text style={styles.subtitle}>
          Configure completeness and rarity alerts. Backend should watch your
          status scores and send notifications when thresholds are hit.
        </Text>

        {loading && (
          <View style={styles.center}>
            <ActivityIndicator />
          </View>
        )}

        {!loading && error && (
          <View style={styles.center}>
            <Text style={styles.error}>{error}</Text>
          </View>
        )}

        {/* Create completeness alert */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Completeness alert</Text>
          <Text style={styles.label}>Collection key</Text>
          <TextInput
            style={styles.input}
            value={collectionKey}
            onChangeText={setCollectionKey}
            placeholder="e.g. Pokémon – Base Set"
          />
          <Text style={styles.label}>
            Trigger when completion >= (%)
          </Text>
          <TextInput
            style={styles.input}
            keyboardType="decimal-pad"
            value={thresholdPct}
            onChangeText={setThresholdPct}
            placeholder="e.g. 95"
          />
          <TouchableOpacity
            onPress={handleCreateCompletenessAlert}
            style={styles.primaryButton}
          >
            <Text style={styles.primaryButtonText}>
              Save completeness alert
            </Text>
          </TouchableOpacity>
        </View>

        {/* Create rarity alert */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Rarity alert</Text>
          <Text style={styles.label}>Category</Text>
          <TextInput
            style={styles.input}
            value={category}
            onChangeText={setCategory}
            placeholder="e.g. Pokemon"
          />
          <Text style={styles.label}>
            Trigger when rarity score >= (%)
          </Text>
          <TextInput
            style={styles.input}
            keyboardType="decimal-pad"
            value={rarityMinPct}
            onChangeText={setRarityMinPct}
            placeholder="e.g. 80"
          />
          <TouchableOpacity
            onPress={handleCreateRarityAlert}
            style={styles.primaryButton}
          >
            <Text style={styles.primaryButtonText}>
              Save rarity alert
            </Text>
          </TouchableOpacity>
        </View>

        {/* Existing alerts list */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Existing alerts</Text>
          {alerts.length === 0 ? (
            <Text style={styles.empty}>
              No alerts configured yet. Create one above.
            </Text>
          ) : (
            alerts.map((a) => (
              <View key={a.id ?? JSON.stringify(a)} style={styles.alertRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.alertTitle}>
                    {a.type === 'completeness'
                      ? 'Completeness'
                      : a.type === 'rarity'
                      ? 'Rarity'
                      : 'Price'}
                  </Text>
                  <Text style={styles.alertMeta}>
                    {a.type === 'completeness' &&
                      `Collection: ${a.collection_key ?? 'n/a'} · >= ${
                        a.threshold_pct ?? 'n/a'
                      }%`}
                    {a.type === 'rarity' &&
                      `Category: ${a.category ?? 'n/a'} · >= ${
                        a.rarity_min_pct ?? 'n/a'
                      }%`}
                    {a.type === 'price' &&
                      `Item: ${a.item_id ?? 'n/a'} · threshold ${
                        a.price_threshold ?? 'n/a'
                      }`}
                  </Text>
                </View>
                {a.enabled && a.id && (
                  <TouchableOpacity
                    onPress={() => handleDisable(a.id!)}
                    style={styles.secondaryButton}
                  >
                    <Text style={styles.secondaryButtonText}>
                      Disable
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f1f5f9',
  },
  content: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  center: {
    marginTop: 24,
    alignItems: 'center',
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#0f172a',
  },
  subtitle: {
    marginTop: 4,
    fontSize: 12,
    color: '#4b5563',
  },
  error: {
    fontSize: 13,
    color: '#b91c1c',
  },
  card: {
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    backgroundColor: '#ffffff',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0f172a',
    marginBottom: 6,
  },
  label: {
    fontSize: 11,
    color: '#374151',
    marginTop: 4,
    marginBottom: 2,
  },
  input: {
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 6,
    fontSize: 13,
    marginBottom: 4,
    backgroundColor: '#f9fafb',
  },
  primaryButton: {
    marginTop: 8,
    borderRadius: 8,
    paddingVertical: 8,
    backgroundColor: '#0ea5e9',
  },
  primaryButtonText: {
    textAlign: 'center',
    fontSize: 12,
    fontWeight: '700',
    color: '#ffffff',
  },
  empty: {
    fontSize: 11,
    color: '#6b7280',
  },
  alertRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
  },
  alertTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#111827',
  },
  alertMeta: {
    fontSize: 11,
    color: '#6b7280',
  },
  secondaryButton: {
    marginLeft: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  secondaryButtonText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#4b5563',
  },
});

export default AlertsDebugScreen;
