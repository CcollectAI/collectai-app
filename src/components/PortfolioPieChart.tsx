/**
 * PortfolioPieChart - Visual breakdown of portfolio by category.
 * Uses SVG for simple pie chart rendering without external chart libraries.
 */

import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { G, Path, Circle } from 'react-native-svg';

interface DataItem {
  category: string;
  value: number;
  color: string;
}

interface Props {
  data: DataItem[];
  size?: number;
  innerRadius?: number;
  colors: {
    text: string;
    muted: string;
    card: string;
  };
}

// Category color palette
const CATEGORY_COLORS: Record<string, string> = {
  'Pokémon': '#FFCB05',
  'Pokemon': '#FFCB05',
  'MTG': '#0D6EFD',
  'Magic: The Gathering': '#0D6EFD',
  'Yugioh': '#9333EA',
  'Yu-Gi-Oh!': '#9333EA',
  'Funko': '#FF6B35',
  'Funko Pop': '#FF6B35',
  'LEGO': '#FF0000',
  'Lego': '#FF0000',
  'Warhammer': '#DC2626',
  'Diecast': '#10B981',
  'Hot Wheels': '#10B981',
  'Sports Cards': '#3B82F6',
  'Lorcana': '#A855F7',
  'Other': '#6B7280',
};

const DEFAULT_COLORS = [
  '#81D8D0', // Tiffany Blue (app accent)
  '#FF6B6B',
  '#4ECDC4',
  '#45B7D1',
  '#96CEB4',
  '#FFEAA7',
  '#DDA0DD',
  '#98D8C8',
  '#F7DC6F',
  '#BB8FCE',
];

function getColorForCategory(category: string, index: number): string {
  return CATEGORY_COLORS[category] || DEFAULT_COLORS[index % DEFAULT_COLORS.length];
}

function polarToCartesian(
  centerX: number,
  centerY: number,
  radius: number,
  angleInDegrees: number
): { x: number; y: number } {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  };
}

function describeArc(
  x: number,
  y: number,
  radius: number,
  startAngle: number,
  endAngle: number
): string {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';

  return [
    'M', start.x, start.y,
    'A', radius, radius, 0, largeArcFlag, 0, end.x, end.y,
    'L', x, y,
    'Z',
  ].join(' ');
}

export function PortfolioPieChart({
  data,
  size = 180,
  innerRadius = 50,
  colors,
}: Props) {
  const total = useMemo(() => data.reduce((sum, d) => sum + d.value, 0), [data]);

  const chartData = useMemo(() => {
    if (total === 0) return [];

    let currentAngle = 0;
    return data.map((item, index) => {
      const percentage = (item.value / total) * 100;
      const angle = (item.value / total) * 360;
      const startAngle = currentAngle;
      const endAngle = currentAngle + angle;
      currentAngle = endAngle;

      return {
        ...item,
        percentage,
        startAngle,
        endAngle,
        color: item.color || getColorForCategory(item.category, index),
      };
    });
  }, [data, total]);

  const centerX = size / 2;
  const centerY = size / 2;
  const radius = (size - 10) / 2;

  if (total === 0) {
    return (
      <View style={[styles.emptyContainer, { width: size, height: size }]}>
        <Text style={[styles.emptyText, { color: colors.muted }]}>No data</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Svg width={size} height={size}>
        <G>
          {chartData.map((slice, index) => {
            // Handle full circle case (single category)
            if (chartData.length === 1) {
              return (
                <Circle
                  key={index}
                  cx={centerX}
                  cy={centerY}
                  r={radius}
                  fill={slice.color}
                />
              );
            }

            // Handle very small slices
            if (slice.endAngle - slice.startAngle < 1) {
              return null;
            }

            return (
              <Path
                key={index}
                d={describeArc(centerX, centerY, radius, slice.startAngle, slice.endAngle)}
                fill={slice.color}
              />
            );
          })}
          {/* Inner circle for donut effect */}
          <Circle cx={centerX} cy={centerY} r={innerRadius} fill={colors.card} />
        </G>
      </Svg>

      {/* Legend */}
      <View style={styles.legend}>
        {chartData.slice(0, 6).map((item, index) => (
          <View key={index} style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: item.color }]} />
            <Text style={[styles.legendLabel, { color: colors.text }]} numberOfLines={1}>
              {item.category}
            </Text>
            <Text style={[styles.legendValue, { color: colors.muted }]}>
              {item.percentage.toFixed(0)}%
            </Text>
          </View>
        ))}
        {chartData.length > 6 && (
          <Text style={[styles.legendMore, { color: colors.muted }]}>
            +{chartData.length - 6} more
          </Text>
        )}
      </View>
    </View>
  );
}

// Simplified chart for small spaces
export function MiniPieChart({
  data,
  size = 48,
}: {
  data: { value: number; color: string }[];
  size?: number;
}) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (total === 0) return null;

  const centerX = size / 2;
  const centerY = size / 2;
  const radius = (size - 4) / 2;

  let currentAngle = 0;
  const chartData = data.map((item) => {
    const angle = (item.value / total) * 360;
    const startAngle = currentAngle;
    const endAngle = currentAngle + angle;
    currentAngle = endAngle;
    return { ...item, startAngle, endAngle };
  });

  return (
    <Svg width={size} height={size}>
      <G>
        {chartData.map((slice, index) => {
          if (chartData.length === 1) {
            return <Circle key={index} cx={centerX} cy={centerY} r={radius} fill={slice.color} />;
          }
          if (slice.endAngle - slice.startAngle < 1) return null;
          return (
            <Path
              key={index}
              d={describeArc(centerX, centerY, radius, slice.startAngle, slice.endAngle)}
              fill={slice.color}
            />
          );
        })}
      </G>
    </Svg>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  emptyContainer: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
  },
  legend: {
    marginTop: 16,
    width: '100%',
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  legendLabel: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
  },
  legendValue: {
    fontSize: 13,
    fontWeight: '600',
    minWidth: 40,
    textAlign: 'right',
  },
  legendMore: {
    fontSize: 12,
    marginTop: 4,
    textAlign: 'center',
  },
});

export default PortfolioPieChart;
