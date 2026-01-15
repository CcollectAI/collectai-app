import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Stack } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';

type QuickScanPrediction = {
  name?: string;
  category_label?: string;
  estimated_low?: number | null;
  estimated_mid?: number | null;
  estimated_high?: number | null;
  currency?: string | null;
  confidence?: number | null;
  price_band_label?: string | null;
};

type QuickScanResult = {
  prediction?: QuickScanPrediction;
  // allow any extra fields from backend without breaking
  [key: string]: any;
};

type DealRating =
  | 'great_deal'
  | 'fair'
  | 'overpriced'
  | 'danger'
  | 'unknown';

type AuthenticityRisk = 'low' | 'medium' | 'high' | 'unknown';

type DealAnalysis = {
  dealRating: DealRating;
  authenticityRisk: AuthenticityRisk;
  fairValue: number | null;
  diffAbs: number | null;
  diffPct: number | null;
  notes: string[];
};

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8081';

function parsePrice(text: string): number | null {
  const cleaned = text.replace(/[^\d.,]/g, '').replace(',', '.');
  if (!cleaned.trim()) return null;
  const value = Number(cleaned);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

function formatCurrency(
  value: number | null | undefined,
  currency: string | null | undefined,
): string {
  if (!value || !Number.isFinite(value)) return '—';
  const cur = currency ?? 'EUR';
  try {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: cur,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${value.toFixed(0)} ${cur}`;
  }
}

function formatPct(
  value: number | null | undefined,
  decimals = 1,
): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const mult = Math.pow(10, decimals);
  const pct = Math.round(value * 100 * mult) / mult;
  return `${pct.toFixed(decimals)}%`;
}

function analyzeDeal(
  quickScan: QuickScanResult | null,
  askingPrice: number | null,
): DealAnalysis | null {
  const prediction = quickScan?.prediction;
  const mid =
    prediction?.estimated_mid ??
    prediction?.estimated_low ??
    prediction?.estimated_high ??
    null;

  if (!mid || !askingPrice) {
    return {
      dealRating: 'unknown',
      authenticityRisk: 'unknown',
      fairValue: mid,
      diffAbs: null,
      diffPct: null,
      notes: [
        'Need both a fair value estimate and the seller’s asking price to evaluate the deal.',
      ],
    };
  }

  const diffAbs = askingPrice - mid;
  const diffPct = diffAbs / mid;
  const confidence = prediction?.confidence ?? null;

  let dealRating: DealRating = 'fair';
  const notes: string[] = [];

  if (diffPct <= -0.25) {
    dealRating = 'great_deal';
    notes.push(
      'Seller price is more than 25% below our mid estimate. This looks like a strong deal on price alone.',
    );
  } else if (diffPct <= 0.1) {
    dealRating = 'fair';
    notes.push(
      'Seller price is within a normal band of our fair value estimate.',
    );
  } else if (diffPct <= 0.3) {
    dealRating = 'overpriced';
    notes.push(
      'Seller price is 10–30% above our estimate. Consider negotiating or comparing with other listings.',
    );
  } else {
    dealRating = 'danger';
    notes.push(
      'Seller price is more than 30% above our estimate. High risk of overpaying unless this is a special variant.',
    );
  }

  let authenticityRisk: AuthenticityRisk = 'low';

  if (!confidence || confidence < 0.4) {
    authenticityRisk = 'medium';
    notes.push(
      'Recognition confidence is low. Double-check edition, print quality, and details manually.',
    );
  }

  const low = prediction?.estimated_low ?? null;
  const high = prediction?.estimated_high ?? null;

  if (
    confidence &&
    confidence < 0.4 &&
    low &&
    askingPrice < low * 0.5
  ) {
    authenticityRisk = 'high';
    notes.push(
      'Price is extremely low vs our estimate with low confidence. High counterfeit / mislisting risk.',
    );
  } else if (
    confidence &&
    confidence >= 0.7 &&
    diffPct > -0.2 &&
    diffPct < 0.2
  ) {
    authenticityRisk = 'low';
    notes.push(
      'Recognition confidence is solid and price sits near fair value. Authenticity risk looks low, but still inspect details.',
    );
  } else if (!confidence) {
    authenticityRisk = 'unknown';
  }

  return {
    dealRating,
    authenticityRisk,
    fairValue: mid,
    diffAbs,
    diffPct,
    notes,
  };
}

export default function AddAuthCheckScreen() {
  const { colors, spacing, radii } = useAppTheme();

  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [quickScan, setQuickScan] = useState<QuickScanResult | null>(
    null,
  );
  const [scanStatus, setScanStatus] = useState<string | null>(null);
  const [scanLoading, setScanLoading] = useState(false);

  const [askingPriceText, setAskingPriceText] = useState('');
  const [analysis, setAnalysis] = useState<DealAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(
    null,
  );

  const handlePickPhoto = useCallback(async () => {
    const { status } =
      await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Camera permission required',
        'Enable camera access to scan collectibles in-store.',
      );
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      quality: 0.8,
    });

    if (result.canceled) return;

    const uri = result.assets?.[0]?.uri ?? null;
    if (!uri) return;

    setPreviewUri(uri);
    setScanStatus('Photo captured. Running QuickScan analysis…');

    setScanLoading(true);
    setQuickScan(null);
    setAnalysis(null);
    setAnalysisError(null);

    try {
      const res = await fetch(
        `${API_BASE_URL}/quickscan-advanced/single`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ demo_mode: true }),
        },
      );

      if (!res.ok) {
        throw new Error(
          `QuickScan failed with status ${res.status}`,
        );
      }

      const json = (await res.json()) as QuickScanResult;
      setQuickScan(json);
      setScanStatus('QuickScan results loaded.');
    } catch (err: any) {
      console.warn('[AddAuthCheck] QuickScan error', err);
      setScanStatus('QuickScan failed. Using demo data instead.');
      setAnalysisError(
        err?.message ?? 'Unable to reach QuickScan service.',
      );
    } finally {
      setScanLoading(false);
    }
  }, []);

  const handleAnalyze = useCallback(() => {
    setAnalysisError(null);
    const asking = parsePrice(askingPriceText);
    if (!asking) {
      setAnalysis(null);
      setAnalysisError(
        'Enter the seller’s asking price to analyze the deal.',
      );
      return;
    }
    const result = analyzeDeal(quickScan, asking);
    if (!result) {
      setAnalysisError(
        'Need both QuickScan data and asking price to evaluate.',
      );
      return;
    }
    setAnalysis(result);
  }, [askingPriceText, quickScan]);

  const prediction = quickScan?.prediction;
  const currency = prediction?.currency ?? 'EUR';

  let dealLabel = 'Waiting for analysis';
  let dealColor = colors.mutedText;
  if (analysis) {
    switch (analysis.dealRating) {
      case 'great_deal':
        dealLabel = 'Great deal';
        dealColor = colors.success ?? '#16a34a';
        break;
      case 'fair':
        dealLabel = 'Fair price';
        dealColor = colors.text;
        break;
      case 'overpriced':
        dealLabel = 'Overpriced';
        dealColor = colors.warning ?? '#C77C00';
        break;
      case 'danger':
        dealLabel = 'Danger: likely overpay';
        dealColor = colors.error ?? '#B00020';
        break;
      case 'unknown':
      default:
        dealLabel = 'Not enough data yet';
        dealColor = colors.mutedText;
        break;
    }
  }

  let authLabel = 'Authenticity: waiting…';
  let authColor = colors.mutedText;
  if (analysis) {
    switch (analysis.authenticityRisk) {
      case 'low':
        authLabel = 'Authenticity risk: low';
        authColor = colors.success ?? '#16a34a';
        break;
      case 'medium':
        authLabel = 'Authenticity risk: medium';
        authColor = colors.warning ?? '#C77C00';
        break;
      case 'high':
        authLabel = 'Authenticity risk: HIGH';
        authColor = colors.error ?? '#B00020';
        break;
      case 'unknown':
      default:
        authLabel = 'Authenticity risk: unknown';
        authColor = colors.mutedText;
        break;
    }
  }

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'In-store authenticity check',
        }}
      />
      <KeyboardAvoidingView
        style={{ flex: 1, backgroundColor: colors.background }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={{
            padding: spacing.lg,
            paddingBottom: spacing.xl * 2,
            gap: spacing.md,
          }}
        >
          {/* Intro / explainer */}
          <View>
            <Text
              style={{
                fontSize: 18,
                fontWeight: '700',
                color: colors.text,
                marginBottom: spacing.xs,
              }}
            >
              Check a deal before you buy
            </Text>
            <Text
              style={{
                fontSize: 13,
                color: colors.mutedText,
              }}
            >
              Use this when you are about to buy a collectible in-store or
              from an online listing. Scan the item, enter the asking
              price, and we will estimate fairness and authenticity risk.
            </Text>
          </View>

          {/* Scan card */}
          <View
            style={{
              borderRadius: radii.lg,
              backgroundColor: colors.card,
              padding: spacing.md,
            }}
          >
            <Text
              style={{
                fontSize: 15,
                fontWeight: '700',
                color: colors.text,
                marginBottom: spacing.sm,
              }}
            >
              1. Scan the item
            </Text>
            {previewUri ? (
              <View
                style={{
                  borderRadius: radii.md,
                  overflow: 'hidden',
                  borderWidth: 1,
                  borderColor: colors.border,
                  marginBottom: spacing.sm,
                }}
              >
                <View
                  style={{
                    height: 180,
                    backgroundColor: colors.surface,
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                >
                  {/* We avoid Image component imports to keep this file self-contained.
                     Replace with <Image> if you prefer a real preview. */}
                  <Text
                    style={{
                      fontSize: 12,
                      color: colors.mutedText,
                      paddingHorizontal: spacing.sm,
                      textAlign: 'center',
                    }}
                  >
                    Photo captured. (Preview hidden in this build to
                    keep dependencies minimal.)
                  </Text>
                </View>
              </View>
            ) : null}
            <TouchableOpacity
              onPress={handlePickPhoto}
              disabled={scanLoading}
              style={{
                borderRadius: radii.full,
                backgroundColor: colors.primary,
                paddingVertical: spacing.sm,
                alignItems: 'center',
                flexDirection: 'row',
                justifyContent: 'center',
                opacity: scanLoading ? 0.7 : 1,
              }}
            >
              {scanLoading ? (
                <ActivityIndicator
                  size="small"
                  color={colors.onPrimary}
                />
              ) : (
                <Text
                  style={{
                    color: colors.onPrimary,
                    fontSize: 14,
                    fontWeight: '600',
                  }}
                >
                  {previewUri ? 'Rescan item' : 'Scan item with camera'}
                </Text>
              )}
            </TouchableOpacity>
            {scanStatus && (
              <Text
                style={{
                  marginTop: spacing.xs,
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                {scanStatus}
              </Text>
            )}

            {prediction?.name && (
              <View style={{ marginTop: spacing.sm }}>
                <Text
                  style={{
                    fontSize: 13,
                    color: colors.mutedText,
                    marginBottom: 2,
                  }}
                >
                  Detected item
                </Text>
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: colors.text,
                  }}
                  numberOfLines={2}
                >
                  {prediction.name}
                </Text>
                {prediction.category_label && (
                  <Text
                    style={{
                      fontSize: 12,
                      color: colors.mutedText,
                      marginTop: 2,
                    }}
                    numberOfLines={1}
                  >
                    {prediction.category_label}
                  </Text>
                )}
              </View>
            )}
          </View>

          {/* Asking price + analysis */}
          <View
            style={{
              borderRadius: radii.lg,
              backgroundColor: colors.card,
              padding: spacing.md,
            }}
          >
            <Text
              style={{
                fontSize: 15,
                fontWeight: '700',
                color: colors.text,
                marginBottom: spacing.sm,
              }}
            >
              2. Enter seller price & analyze
            </Text>

            <View style={{ marginBottom: spacing.sm }}>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginBottom: 4,
                }}
              >
                Seller asking price ({currency})
              </Text>
              <TextInput
                value={askingPriceText}
                onChangeText={setAskingPriceText}
                keyboardType="decimal-pad"
                placeholder="e.g. 120"
                placeholderTextColor={colors.mutedText}
                style={{
                  borderRadius: radii.md,
                  borderWidth: 1,
                  borderColor: colors.border,
                  paddingHorizontal: spacing.sm,
                  paddingVertical: spacing.xs,
                  fontSize: 14,
                  color: colors.text,
                }}
              />
            </View>

            <TouchableOpacity
              onPress={handleAnalyze}
              style={{
                borderRadius: radii.full,
                backgroundColor: colors.primary,
                paddingVertical: spacing.sm,
                alignItems: 'center',
              }}
            >
              <Text
                style={{
                  color: colors.onPrimary,
                  fontSize: 14,
                  fontWeight: '600',
                }}
              >
                Analyze deal
              </Text>
            </TouchableOpacity>

            {analysisError && (
              <Text
                style={{
                  marginTop: spacing.xs,
                  fontSize: 12,
                  color: colors.error ?? '#B00020',
                }}
              >
                {analysisError}
              </Text>
            )}

            {/* Deal summary */}
            <View
              style={{
                marginTop: spacing.md,
                paddingTop: spacing.sm,
                borderTopWidth: 1,
                borderTopColor: colors.border,
              }}
            >
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginBottom: 4,
                }}
              >
                Deal summary
              </Text>
              <Text
                style={{
                  fontSize: 16,
                  fontWeight: '700',
                  color: dealColor,
                  marginBottom: spacing.xs,
                }}
              >
                {dealLabel}
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: authColor,
                  marginBottom: spacing.xs,
                }}
              >
                {authLabel}
              </Text>

              <View style={{ marginTop: spacing.xs }}>
                <Text
                  style={{
                    fontSize: 12,
                    color: colors.mutedText,
                    marginBottom: 2,
                  }}
                >
                  Our fair value estimate
                </Text>
                <Text
                  style={{
                    fontSize: 14,
                    fontWeight: '600',
                    color: colors.text,
                    marginBottom: 2,
                  }}
                >
                  {formatCurrency(
                    analysis?.fairValue ??
                      prediction?.estimated_mid ??
                      null,
                    currency,
                  )}
                </Text>
                {analysis?.diffAbs != null &&
                  analysis.diffPct != null && (
                    <Text
                      style={{
                        fontSize: 12,
                        color: colors.mutedText,
                      }}
                    >
                      Seller is {formatCurrency(
                        Math.abs(analysis.diffAbs),
                        currency,
                      )}{' '}
                      {analysis.diffAbs > 0 ? 'above' : 'below'} our
                      estimate ({formatPct(analysis.diffPct)}).
                    </Text>
                  )}
              </View>
            </View>
          </View>

          {/* Manual authenticity checklist */}
          <View
            style={{
              borderRadius: radii.lg,
              backgroundColor: colors.card,
              padding: spacing.md,
              marginBottom: spacing.lg,
            }}
          >
            <Text
              style={{
                fontSize: 15,
                fontWeight: '700',
                color: colors.text,
                marginBottom: spacing.sm,
              }}
            >
              3. Manual authenticity checklist
            </Text>
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
                marginBottom: spacing.xs,
              }}
            >
              Even with AI help, always verify the item in front of you:
            </Text>
            <View style={{ marginLeft: spacing.sm, gap: 4 }}>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                • Compare edges, printing quality, and colors to a known
                authentic example.
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                • For cards: check centering, holo pattern, and font
                crispness.
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                • For figures/model kits: inspect seams, paint lines, and
                logos for sloppiness.
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                • If price looks too good to be true and risk is high,
                walk away or ask for more proof.
              </Text>
            </View>

            {analysis?.notes?.length ? (
              <View style={{ marginTop: spacing.sm }}>
                <Text
                  style={{
                    fontSize: 12,
                    color: colors.mutedText,
                    marginBottom: 4,
                  }}
                >
                  Extra notes for this item
                </Text>
                {analysis.notes.map((n, idx) => (
                  <Text
                    key={idx}
                    style={{
                      fontSize: 12,
                      color: colors.mutedText,
                      marginBottom: 2,
                    }}
                  >
                    • {n}
                  </Text>
                ))}
              </View>
            ) : null}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </>
  );
}
