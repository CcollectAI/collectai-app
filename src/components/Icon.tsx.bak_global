import React from 'react';
import {
  LineChart, Images, PlusCircle, ShoppingCart, Settings, Share2,
  ChevronDown, X, Check, Image as ImageIcon, Search, Shield
} from 'lucide-react-native';

type Name =
  | 'stats-chart-outline' | 'albums-outline' | 'add-circle-outline' | 'cart-outline'
  | 'settings-outline' | 'share-outline' | 'chevron-down' | 'close'
  | 'checkmark' | 'image-outline' | 'search-outline' | 'shield-outline';

export default function Icon({ name, size = 20, color = '#0B3D91' }:{name:Name; size?:number; color?:string}) {
  const p = { size, color };
  switch (name) {
    case 'stats-chart-outline': return <LineChart {...p} />;
    case 'albums-outline':      return <Images {...p} />;
    case 'add-circle-outline':  return <PlusCircle {...p} />;
    case 'cart-outline':        return <ShoppingCart {...p} />;
    case 'settings-outline':    return <Settings {...p} />;
    case 'share-outline':       return <Share2 {...p} />;
    case 'chevron-down':        return <ChevronDown {...p} />;
    case 'close':               return <X {...p} />;
    case 'checkmark':           return <Check {...p} />;
    case 'image-outline':       return <ImageIcon {...p} />;
    case 'search-outline':      return <Search {...p} />;
    case 'shield-outline':      return <Shield {...p} />;
    default: return null;
  }
}
