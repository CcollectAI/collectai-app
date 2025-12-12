import React from 'react';
import Ionicons from '@expo/vector-icons/Ionicons';

type Tier = 'silver' | 'gold' | 'bronze';
export default function ShieldBadge({ tier='silver', size=18 }: { tier?: Tier; size?: number }){
  const color =
    tier === 'gold' ? '#D4AF37' :
    tier === 'bronze' ? '#CD7F32' :
    '#C0C0C0';
  return <Ionicons name="shield" size={size} color={color} />;
}
