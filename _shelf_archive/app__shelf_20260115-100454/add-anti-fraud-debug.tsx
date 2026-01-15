import React, { useState } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import AntiFraudCard from '@/components/AntiFraudCard';
import { QuickScanPrediction } from '@/utils/antiFraud';

/**
 * This screen is a playground to wire anti-fraud into the Add flow.
 * It uses a stub QuickScanPrediction; you can swap in the real one from
 * /quickscan-advanced/single later.
 */
const AddAntiFraudDebugScreen: React.FC = () => {
  const [askingPriceText, setAskingPriceText] = useState('');
  const [costBasisText, setCostBasisText] = useState('');

  const askingPrice = parseFloat(askingPriceText.replace(',', '.'));
  const costBasis = parseFloat(costBasisText.replace(',', '.'));

  const quickscan: QuickScanPrediction = {
    name: 'Demo Black Lotus',
    estimated_mid: 1200,
    estimated_low: 900,
    estimated_high: 1500,
    currency: 'EUR',
    confidence: 0.8,
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Add – Anti-fraud debug</Text>
        <Text style={styles.subtitle}>
          This is a sandbox for the real Add flow. Replace the stub
          QuickScan prediction with your actual scan result when wiring
          app/(tabs)/add.tsx.
        </Text>

        <View style={styles.card}>
          <Text style={styles.label}>Asking price (IRL)</Text>
          <TextInput
            style={styles.input}
            keyboardType="decimal-pad"
            placeholder="e.g. 1300"
            value={askingPriceText}
            onChangeText={setAskingPriceText}
          />
          <Text style={styles.label}>Your cost basis (optional)</Text>
          <TextInput
            style={styles.input}
            keyboardType="decimal-pad"
            placeholder="e.g. 800"
            value={costBasisText}
            onChangeText={setCostBasisText}
          />
        </View>

        <AntiFraudCard
          input={{
            prediction: quickscan,
            askingPrice:
              Number.isFinite(askingPrice) ? askingPrice : null,
            costBasis:
              Number.isFinite(costBasis) ? costBasis : null,
          }}
        />
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
    fontSize: 12,
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
    marginBottom: 8,
    backgroundColor: '#f9fafb',
  },
});

export default AddAntiFraudDebugScreen;
