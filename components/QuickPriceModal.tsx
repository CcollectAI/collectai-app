import React, { useState } from 'react';
import { Modal, View, Text, TextInput, Button, Alert } from 'react-native';
import { addManualPrice } from '../lib/price';

export default function QuickPriceModal({ visible, onClose, itemId }: { visible: boolean; onClose: () => void; itemId: string }) {
  const [val, setVal] = useState('');

  async function save() {
    try {
      const n = Number(val);
      if (!(n >= 0)) { Alert.alert('Invalid', 'Enter a number.'); return; }
      await addManualPrice(itemId, n, 'EUR');
      setVal('');
      onClose();
    } catch (e:any) {
      Alert.alert('Error', e.message ?? String(e));
    }
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex:1, backgroundColor:'rgba(0,0,0,0.4)', justifyContent:'center', padding:16 }}>
        <View style={{ backgroundColor:'#fff', borderRadius:12, padding:16, gap:12 }}>
          <Text style={{ fontWeight:'700', fontSize:16 }}>Add Price (EUR)</Text>
          <TextInput
            value={val}
            onChangeText={setVal}
            keyboardType="decimal-pad"
            placeholder="e.g., 49.99"
            style={{ borderWidth:1, borderColor:'#ddd', padding:10, borderRadius:8 }}
          />
          <View style={{ flexDirection:'row', justifyContent:'flex-end', gap:8 }}>
            <Button title="Cancel" onPress={onClose} />
            <Button title="Save" onPress={save} />
          </View>
        </View>
      </View>
    </Modal>
  );
}
