import { useState, useMemo } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, Image, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import Card from '@/components/Card';
import { theme } from '@/theme';
import { addItem } from '@/store/items';
import { predictFromImage } from '@/lib/predict';
import { router } from 'expo-router';
import CompactSelect from '@/components/CompactSelect';

const CATEGORIES = ['Pokémon', 'Funko', 'LEGO', 'Diecast', 'Sports Cards', 'Comics', 'Other'];
const CONDITIONS = ['New', 'Near Mint', 'Used', 'Damaged'];
const EDITIONS = ['Base', 'First Edition', 'Limited', 'Promo', 'Special'];
const GRADES = ['Raw', 'PSA 10', 'PSA 9', 'BGS 9.5', 'BGS 9', 'SGC 10', 'CGC 9.5'];

export default function Add() {
  const YEARS = useMemo(() => Array.from({ length: 60 }, (_, i) => String(new Date().getFullYear() - i)), []);
  const [photo, setPhoto] = useState<string | null>(null);
  const [predCat, setPredCat] = useState<string | null>(null);
  const [predVal, setPredVal] = useState<number | null>(null);
  const [predicting, setPredicting] = useState(false);

  // Manual fields
  const [category, setCategory] = useState<string>('Pokémon');
  const [title, setTitle] = useState<string>('');
  const [condition, setCondition] = useState<string>('New');
  const [year, setYear] = useState<string>(YEARS[0]);
  const [brand, setBrand] = useState<string>('');
  const [series, setSeries] = useState<string>(''); // Set/Series
  const [edition, setEdition] = useState<string>(EDITIONS[0]);
  const [grade, setGrade] = useState<string>(GRADES[0]);
  const [purchase, setPurchase] = useState<string>('');   // string for TextInput
  const [estValue, setEstValue] = useState<string>('');   // overridable
  const [notes, setNotes] = useState<string>('');

  const fmtEUR0 = (n: number) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0, minimumFractionDigits: 0 }).format(n);

  const handlePick = async (mode: 'camera' | 'library') => {
    try {
      if (mode === 'camera') {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') return Alert.alert('Permission needed', 'Camera access is required.');
        const res = await ImagePicker.launchCameraAsync({ quality: 0.6 });
        if (res.canceled) return;
        const uri = res.assets[0].uri;
        setPhoto(uri);
        await runPredict(uri);
      } else {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') return Alert.alert('Permission needed', 'Library access is required.');
        const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.6 });
        if (res.canceled) return;
        const uri = res.assets[0].uri;
        setPhoto(uri);
        await runPredict(uri);
      }
    } catch (e) {
      Alert.alert('Error', 'Could not open camera or library.');
    }
  };

  const runPredict = async (uri: string) => {
    setPredicting(true);
    try {
      const p = await predictFromImage(uri);
      setPredCat(p.category);
      setPredVal(p.estValue);
    } finally {
      setPredicting(false);
    }
  };

  const applyPrediction = () => {
    if (predCat) setCategory(predCat);
    if (predVal !== null) setEstValue(String(predVal));
  };

  const onSave = () => {
    if (!title.trim()) return Alert.alert('Missing title', 'Please enter an item title.');
    const price = Number(estValue || 0);
    const buy = Number(purchase || 0);
    const pct = buy > 0 ? ((price - buy) / buy) * 100 : undefined;

    // Persist minimal item (name/price/%/notes). Extra metadata can be appended into notes.
    const meta = [`Category: ${category}`, year && `Year: ${year}`, brand && `Brand: ${brand}`, series && `Set/Series: ${series}`, edition && `Edition: ${edition}`, grade && `Grade: ${grade}`].filter(Boolean).join(' • ');
    const mergedNotes = [notes.trim(), meta].filter(Boolean).join('\n');

    addItem({
      category,
      name: title.trim(),
      price: isNaN(price) ? 0 : Math.round(price),
      pct: typeof pct === 'number' && isFinite(pct) ? pct : undefined,
      notes: mergedNotes || undefined,
    });

    Alert.alert('Saved', 'Item added to your collection.', [
      { text: 'View Items', onPress: () => router.navigate('/(tabs)/items') },
      { text: 'OK' },
    ]);
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* AI photo valuation — headline feature (alignment improved) */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>
          Use AI Prediction & Take a picture
        </Text>

        {/* Capture actions: wrap on small widths, aligned left */}
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.spacing.md }}>
          <Pressable onPress={() => handlePick('camera')} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Take photo</Text>
          </Pressable>
          <Pressable onPress={() => handlePick('library')} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Choose from library</Text>
          </Pressable>
        </View>

        {/* Preview + prediction */}
        {photo ? (
          <View style={{ gap: theme.spacing.sm }}>
            <Image source={{ uri: photo }} style={{ width: '100%', height: 200, borderWidth: 1, borderColor: theme.colors.border }} />
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Text style={{ color: theme.colors.subtext }}>{predicting ? 'Predicting…' : predCat ? `Predicted: ${predCat}` : 'No prediction yet'}</Text>
              <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>
                {predVal != null ? fmtEUR0(predVal) : ''}
              </Text>
            </View>
            <View>
              <Pressable onPress={applyPrediction} disabled={!predCat && predVal==null} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl, alignSelf: 'flex-start', opacity: (!predCat && predVal==null) ? 0.5 : 1 }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Apply suggestion</Text>
              </Pressable>
            </View>
          </View>
        ) : null}
      </Card>

      {/* Manual entry — compact dropdowns + vertical fields */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Manual entry</Text>

        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Category</Text>
        <CompactSelect title="Select Category" options={CATEGORIES} value={category} onChange={setCategory} searchable />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Item title</Text>
        <TextInput value={title} onChangeText={setTitle} placeholder="e.g., PSA 9 Charizard" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />

        {/* Collector details */}
        <View style={{ gap: theme.spacing.md }}>
          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Year</Text>
            <CompactSelect title="Year" options={YEARS} value={year} onChange={setYear} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Brand</Text>
            <TextInput value={brand} onChangeText={setBrand} placeholder="e.g., PSA, Topps, LEGO" placeholderTextColor={theme.colors.subtext}
              style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Set / Series</Text>
            <TextInput value={series} onChangeText={setSeries} placeholder="e.g., Base Set, UCS" placeholderTextColor={theme.colors.subtext}
              style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Edition</Text>
            <CompactSelect title="Edition" options={EDITIONS} value={edition} onChange={setEdition} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Grading</Text>
            <CompactSelect title="Grading" options={GRADES} value={grade} onChange={setGrade} />
          </View>
        </View>

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Condition</Text>
        <CompactSelect title="Select Condition" options={CONDITIONS} value={condition} onChange={setCondition} />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Purchase price (EUR)</Text>
        <TextInput value={purchase} onChangeText={setPurchase} keyboardType="decimal-pad" placeholder="e.g., 300" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Estimated value (EUR)</Text>
        <TextInput value={estValue} onChangeText={setEstValue} keyboardType="decimal-pad" placeholder="e.g., 950" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Notes</Text>
        <TextInput value={notes} onChangeText={setNotes} multiline placeholder="Any extra details..." placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, height: 100, textAlignVertical: 'top' }} />
      </Card>

      {/* Save */}
      <View style={{ alignItems: 'center' }}>
        <Pressable onPress={onSave} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Add to Items</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
