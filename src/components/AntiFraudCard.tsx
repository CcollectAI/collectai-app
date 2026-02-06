import React, { useMemo } from 'react';
import { View, Text } from 'react-native';
import {
  AntiFraudInput,
  AntiFraudResult,
  computeAntiFraudSignal,
} from '@/utils/antiFraud';
import {
  buildAntiFraudEventFromResult,
  logAntiFraudEvent,
  AntiFraudUserDecision,
} from '@/services/antiFraudClient';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

interface Props {
  input: AntiFraudInput | null;
  /**
   * Optional callback when user chooses an action.
   * Good place to branch Add flow (e.g. "avoid" => don't save item).
   */
  onDecision?: (decision: AntiFraudUserDecision, result: AntiFraudResult) => void;
  /** Optional context for logging. */
  itemName?: string | null;
  category?: string | null;
  quickscanId?: string | null;
  currency?: string | null;
}

export const AntiFraudCard: React.FC<Props> = ({
  input,
  onDecision,
  itemName,
  category,
  quickscanId,
  currency,
}) => {
  const { settings } = useSettings();
  const result: AntiFraudResult | null = useMemo(() => {
    if (!input) return null;
    return computeAntiFraudSignal(input);
  }, [input]);

  if (!input) {
    return (
      <View
        style={{
          marginTop: 12,
          padding: 12,
          borderRadius: 12,
          backgroundColor: '#f3f4f6',
        }}
      >
        <Text
          style={{
            fontSize: 13,
            fontWeight: '600',
            marginBottom: 4,
          }}
        >
          Anti-fraud check
        </Text>
        <Text
          style={{
            fontSize: 11,
            color: '#4b5563',
          }}
        >
          Scan an item and enter the asking price to see a fraud risk
          estimate.
        </Text>
      </View>
    );
  }

  if (!result) return null;

  const { risk, score, summary, details } = result;

  let bg = '#dcfce7';
  let titleColor = '#166534';

  if (risk === 'medium') {
    bg = '#fef9c3';
    titleColor = '#92400e';
  } else if (risk === 'high') {
    bg = '#fee2e2';
    titleColor = '#b91c1c';
  }

  const riskLabel =
    risk === 'low'
      ? 'Low risk'
      : risk === 'medium'
      ? 'Medium risk'
      : 'High risk';

  const handleDecision = async (decision: AntiFraudUserDecision) => {
    const eventPayload = buildAntiFraudEventFromResult({
      result,
      decision,
      itemName: itemName ?? null,
      category: category ?? null,
      quickscanId: quickscanId ?? null,
      currency: currency ?? null,
    });
    logAntiFraudEvent(eventPayload).catch(() => {});

    if (onDecision) {
      onDecision(decision, result);
    }
  };

  return (
    <View
      style={{
        marginTop: 12,
        padding: 12,
        borderRadius: 12,
        backgroundColor: bg,
      }}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          marginBottom: 4,
        }}
      >
        <Text
          style={{
            flex: 1,
            fontSize: 13,
            fontWeight: '700',
            color: titleColor,
          }}
        >
          Anti-fraud check
        </Text>
        <Text
          style={{
            fontSize: 12,
            fontWeight: '700',
            color: titleColor,
          }}
        >
          {riskLabel} · {Math.round(score)} / 100
        </Text>
      </View>

      <Text
        style={{
          fontSize: 11,
          color: '#111827',
          marginBottom: 6,
        }}
      >
        {summary}
      </Text>

      <View
        style={{
          marginTop: 4,
          flexDirection: 'row',
          flexWrap: 'wrap',
        }}
      >
        {details.estimatedMid != null && (
          <Text
            style={{
              fontSize: 10,
              color: '#374151',
              marginRight: 8,
            }}
          >
            Model mid: {details.estimatedMid.toFixed(2)}
          </Text>
        )}
        {details.askingPrice != null && (
          <Text
            style={{
              fontSize: 10,
              color: '#374151',
              marginRight: 8,
            }}
          >
            Asking: {details.askingPrice.toFixed(2)}
          </Text>
        )}
        {details.premiumPct != null && (
          <Text
            style={{
              fontSize: 10,
              color: '#374151',
              marginRight: 8,
            }}
          >
            Premium: {details.premiumPct.toFixed(1)}%
          </Text>
        )}
        {details.discountPct != null &&
          details.discountPct > 0 && (
            <Text
              style={{
                fontSize: 10,
                color: '#374151',
                marginRight: 8,
              }}
            >
              Discount: {details.discountPct.toFixed(1)}%
            </Text>
          )}
        {details.confidence != null && (
          <Text
            style={{
              fontSize: 10,
              color: '#374151',
              marginRight: 8,
            }}
          >
            Model confidence:{' '}
            {Math.round(details.confidence * 100)}%
          </Text>
        )}
      </View>

      <View
        style={{
          marginTop: 8,
          flexDirection: 'row',
          justifyContent: 'space-between',
        }}
      >
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            handleDecision('avoid');
          }}
          style={{
            flex: 1,
            paddingVertical: 6,
            borderRadius: 8,
            backgroundColor: '#ef4444',
            marginRight: 4,
          }}
        >
          <Text
            style={{
              textAlign: 'center',
              fontSize: 11,
              fontWeight: '700',
              color: '#ffffff',
            }}
          >
            Avoid purchase
          </Text>
        </AnimatedPressable>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            handleDecision('negotiate');
          }}
          style={{
            flex: 1,
            paddingVertical: 6,
            borderRadius: 8,
            backgroundColor: '#f97316',
            marginHorizontal: 4,
          }}
        >
          <Text
            style={{
              textAlign: 'center',
              fontSize: 11,
              fontWeight: '700',
              color: '#ffffff',
            }}
          >
            Negotiate
          </Text>
        </AnimatedPressable>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
            handleDecision('proceed');
          }}
          style={{
            flex: 1,
            paddingVertical: 6,
            borderRadius: 8,
            backgroundColor: '#22c55e',
            marginLeft: 4,
          }}
        >
          <Text
            style={{
              textAlign: 'center',
              fontSize: 11,
              fontWeight: '700',
              color: '#ffffff',
            }}
          >
            Proceed
          </Text>
        </AnimatedPressable>
      </View>
    </View>
  );
};

export default AntiFraudCard;
