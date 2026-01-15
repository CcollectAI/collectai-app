import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

const API_URL =
  // Expo web / native env
  process.env.EXPO_PUBLIC_API_URL ||
  // Fallback: same host as the app (mostly for web)
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8081`
    : 'http://localhost:8081');

const BackendDebugScreen: React.FC = () => {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>(
    'idle',
  );
  const [message, setMessage] = useState<string>('');
  const [raw, setRaw] = useState<string>('');

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      setStatus('loading');
      setMessage('');
      setRaw('');
      try {
        const url = `${API_URL}/healthz`;
        setMessage(`GET ${url}`);
        const res = await fetch(url);
        const text = await res.text();
        if (cancelled) return;
        setRaw(text);
        if (!res.ok) {
          setStatus('error');
          setMessage((m) => `${m} → HTTP ${res.status}`);
        } else {
          setStatus('ok');
          setMessage((m) => `${m} → HTTP ${res.status}`);
        }
      } catch (e: any) {
        if (cancelled) return;
        setStatus('error');
        setMessage(`Request failed: ${e?.message || String(e)}`);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Backend debug</Text>
        <Text style={styles.subtitle}>
          Checking /healthz on your API. This helps confirm if the app can reach
          the collectors-merge backend from this device.
        </Text>

        <View style={styles.card}>
          <Text style={styles.label}>EXPO_PUBLIC_API_URL</Text>
          <Text style={styles.value}>{API_URL}</Text>

          <Text style={[styles.label, { marginTop: 8 }]}>Status</Text>
          <Text style={styles.value}>{status}</Text>

          <Text style={[styles.label, { marginTop: 8 }]}>Message</Text>
          <Text style={styles.value}>{message}</Text>

          {status === 'loading' && (
            <View style={styles.center}>
              <ActivityIndicator />
            </View>
          )}

          {raw ? (
            <>
              <Text style={[styles.label, { marginTop: 8 }]}>
                Raw response
              </Text>
              <Text style={styles.raw}>{raw}</Text>
            </>
          ) : null}
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
  card: {
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    backgroundColor: '#ffffff',
  },
  label: {
    fontSize: 11,
    color: '#6b7280',
  },
  value: {
    fontSize: 12,
    color: '#111827',
  },
  raw: {
    marginTop: 4,
    fontSize: 11,
    color: '#111827',
  },
  center: {
    marginTop: 8,
    alignItems: 'center',
  },
});

export default BackendDebugScreen;
