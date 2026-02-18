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

export async function uploadImageToBucket(params: {
  uid: string;
  uri: string;
  bucket?: string;
}) {
  const { uid, uri, bucket = 'item-images' } = params;

  // pick extension
  const ext = (uri.split('.').pop() || 'jpg').toLowerCase();
  const path = `${uid}/${Date.now()}.${ext}`;

  // read file → base64 → Uint8Array
  const base64 = await FileSystem.readAsStringAsync(uri, {
    encoding: 'base64',
  });
  const bytes = base64ToUint8Array(base64);

  // upload (no upsert header to avoid server complaints)
  const { error } = await supabase
    .storage
    .from(bucket)
    .upload(path, bytes, { contentType: `image/${ext === 'jpg' ? 'jpeg' : ext}` });

  if (error) throw error;

  const { data: { publicUrl } } = supabase.storage.from(bucket).getPublicUrl(path);
  return publicUrl as string;
}

