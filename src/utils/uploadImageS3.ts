/**
 * S3 presigned-PUT image upload — replacement for the Supabase Storage
 * `uploadImage*.ts` utilities.
 *
 * Flow:
 *  1. Ask backend for a presigned PUT URL (POST /uploads/presign)
 *  2. Read the local file as binary, PUT it to S3 directly with the
 *     correct Content-Type header
 *  3. Return the S3 public URL for storing in DB
 *
 * Supabase migration: callsites switch by changing `from "@/utils/upload*"`
 * to `from "@/utils/uploadImageS3"`. The 3 legacy utils stay alive for
 * backward compat until every call is migrated, then they get deleted.
 */
import * as FileSystem from 'expo-file-system';
import { decode as atob } from 'base-64';

import { post } from '@/api/httpClient';

type UploadKind =
  | 'item-images'
  | 'listing-images'
  | 'feed-images'
  | 'refs'
  | 'user-content'
  | 'captures';

function base64ToUint8Array(base64: string) {
  const bin = atob(base64);
  const len = bin.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function inferContentType(uri: string): string {
  const ext = (uri.split('.').pop() || 'jpg').toLowerCase();
  if (ext === 'jpg') return 'image/jpeg';
  if (ext === 'heic' || ext === 'heif' || ext === 'png' || ext === 'webp' || ext === 'jpeg') {
    return `image/${ext}`;
  }
  return 'image/jpeg';
}

export async function uploadImageToS3(params: {
  kind: UploadKind;
  uri: string;
}): Promise<string> {
  const { kind, uri } = params;

  // Stable filename — include extension so S3's signed URL preserves it.
  const ext = (uri.split('.').pop() || 'jpg').toLowerCase();
  const filename = `${Date.now()}.${ext}`;
  const contentType = inferContentType(uri);

  // 1. Presign
  const presign: any = await post('/uploads/presign', {
    kind,
    filename,
    content_type: contentType,
  });
  if (!presign?.upload_url || !presign?.public_url) {
    throw new Error('Presign response missing upload_url or public_url');
  }

  // 2. Read local file as bytes
  const base64 = await FileSystem.readAsStringAsync(uri, { encoding: 'base64' });
  const bytes = base64ToUint8Array(base64);

  // 3. PUT directly to S3. Important: Content-Type must match what we
  //    asked for in presign — S3 rejects mismatched headers.
  const resp = await fetch(presign.upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': contentType },
    body: bytes as any,
  });
  if (!resp.ok) {
    throw new Error(`S3 PUT failed: ${resp.status} ${await resp.text()}`);
  }

  return presign.public_url as string;
}
