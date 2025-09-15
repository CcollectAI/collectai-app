import React from 'react';
import {
  LineChart,    // stats-chart-outline
  Images,       // albums-outline
  PlusCircle,   // add-circle-outline
  ShoppingCart, // cart-outline
  Settings,     // settings-outline
  Share2,       // share-outline
  ChevronDown,  // chevron-down
  X,            // close
  Check,        // checkmark
  Image as ImageIcon, // image-outline
  Search,       // search-outline
  Shield        // shield-outline
} from 'lucide-react-native';

type Props = {
  name:
    | 'stats-chart-outline' | 'albums-outline' | 'add-circle-outline' | 'cart-outline'
    | 'settings-outline' | 'share-outline' | 'chevron-down' | 'close'
    | 'checkmark' | 'image-outline' | 'search-outline' | 'shield-outline';
  size?: number;
  color?: string;
};

export default function Icon({ name, size = 20, color = '#0B3D91' }: Props) {
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
