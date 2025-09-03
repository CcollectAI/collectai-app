import React, { useEffect, useState } from 'react';
import { Image, View } from 'react-native';
import { getSignedUrl } from '../lib/storage';

export default function ThumbImage({ path, size=84, radius=10 }: { path?: string|null; size?: number; radius?: number }) {
  const [uri, setUri] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!path) { setUri(null); return; }
      try {
        const u = await getSignedUrl(path, 3600);
        if (mounted) setUri(u);
      } catch { if (mounted) setUri(null); }
    })();
    return () => { mounted = false; };
  }, [path]);

  if (!uri) return <View style={{ width: size, height: size, borderRadius: radius, backgroundColor: '#f4f4f4' }} />;
  return <Image source={{ uri }} style={{ width: size, height: size, borderRadius: radius }} />;
}
