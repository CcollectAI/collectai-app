import * as FileSystem from 'expo-file-system';
import { decode as atob } from 'base-64';
import { supabase } from "@/lib/supabase";

function base64ToUint8Array(base64: string) {
  const bin = atob(base64);
  const len = bin.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

export async function uploadFeedImage(uid: string, uri: string) {
  const ext = (uri.split('.').pop() || 'jpg').toLowerCase();
  const path = `${uid}/${Date.now()}.${ext}`;
  const base64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
  const bytes = base64ToUint8Array(base64);
  const { error } = await supabase.storage.from('feed-images').upload(path, bytes, { contentType: `image/${ext==='jpg'?'jpeg':ext}` });
  if (error) throw error;
  const { data: { publicUrl } } = supabase.storage.from('feed-images').getPublicUrl(path);
  return publicUrl as string;
}
