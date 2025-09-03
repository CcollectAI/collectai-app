import { View } from 'react-native';
import { LineChart } from 'react-native-gifted-charts';
import { colors, radius } from '../theme/tokens';

export type Point = { value: number };

export default function PortfolioChart({ data }:{ data: Point[] }) {
  return (
    <View style={{ backgroundColor: '#fff', borderRadius: radius.lg, borderWidth:1, borderColor:'#E2E8F0', padding: 8 }}>
      <LineChart
        data={data}
        thickness={3}
        hideRules
        hideYAxisText
        hideDataPoints
        color={colors.accentStrong}
        curved
        initialSpacing={8}
        endSpacing={8}
        yAxisColor="transparent"
        xAxisColor="transparent"
        noOfSections={4}
        spacing={32}
        areaChart
        startFillColor={colors.accent}
        endFillColor="#ffffff00"
        startOpacity={0.3}
        endOpacity={0.0}
      />
    </View>
  );
}
