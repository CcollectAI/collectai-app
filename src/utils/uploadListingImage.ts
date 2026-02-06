import * as FileSystem from 'expo-file-system';
import { decode as atob } from 'base-64';
import { supabase } from "@/lib/supabase";

function b64ToBytes(b64:string){
  const bin = atob(b64); const out = new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) out[i]=bin.charCodeAt(i);
  return out;
}

export async function uploadListingImage(uid:string, uri:string){
  const ext = (uri.split('.').pop() || 'jpg').toLowerCase();
  const path = `${uid}/${Date.now()}.${ext}`;
  const base64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
  const bytes = b64ToBytes(base64);
  const { error } = await supabase.storage.from('listing-images').upload(path, bytes, { contentType:`image/${ext==='jpg'?'jpeg':ext}` });
  if (error) throw error;
  const { data:{ publicUrl } } = supabase.storage.from('listing-images').getPublicUrl(path);
  return publicUrl as string;
}
