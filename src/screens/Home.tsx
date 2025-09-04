import { View, Text, ActivityIndicator } from 'react-native';
import Header from '../components/Header';
import ActionTile from '../components/ActionTile';
import Tile from '../components/Tile';
import Badge from '../components/Badge';
import PortfolioChart from '../components/PortfolioChart';
import usePortfolio from '../hooks/usePortfolio';
import usePortfolioSeries from '../hooks/usePortfolioSeries';
import { colors, spacing } from '../theme/tokens';
import { useNavigation } from '@react-navigation/native';

export default function Home(){
  const { data, loading, error } = usePortfolio();
  const { series, loading: loadingSeries } = usePortfolioSeries();
  const nav = useNavigation<any>();

  if (loading || loadingSeries) {
    return (
      <View style={{flex:1,justifyContent:'center',alignItems:'center'}}>
        <ActivityIndicator/>
      </View>
    );
  }
  if (error) return <View style={{padding:24}}><Text>{error}</Text></View>;

  const delta = (Number(data?.total_value||0) - Number(data?.total_spent||0));
  const tone = (delta >= 0 ? 'pos' : 'neg') as 'pos'|'neg';
  const deltaText = `${delta >= 0 ? '+' : ''}$${delta.toFixed(2)}`;

  return (
    <View style={{ flex:1, backgroundColor: colors.bg }}>
      <Header title="Your Portfolio" subtitle="Track, value, predict" />

      <View style={{ paddingHorizontal: spacing(2), gap: spacing(1) }}>
        <Tile
          value={`$${Number(data?.total_value||0).toFixed(2)}`}
          label="Total value"
          right={<Badge text={deltaText} tone={tone} />}
        />
        <Tile value={`${data?.total_items||0}`} label="Items" />
      </View>

      <View style={{ padding: spacing(2), gap: spacing(1) }}>
        <PortfolioChart data={series} />
        <ActionTile
          title="Open Marketplace"
          subtitle="Browse listings, make offers"
          icon="pricetags-outline"
          onPress={() => nav.navigate('Marketplace')}
        />
      </View>
    </View>
  );
}
