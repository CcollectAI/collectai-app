/**
 * Hook for uploading user photos with server-side optimization.
 *
 * Primary flow (server-side optimized):
 * 1. User picks a photo from camera or gallery (via expo-image-picker)
 * 2. Frontend POSTs image to /photos/upload (multipart)
 * 3. Server resizes to 1200px max edge, converts to JPEG q85, strips EXIF
 * 4. Server generates a blurhash placeholder and uploads to S3
 * 5. Returns CDN URL + blurhash + dimensions
 *
 * Fallback flow (presigned URL — used if server-side upload fails):
 * 1. Frontend calls /photos/presign-upload for a presigned S3 PUT URL
 * 2. Frontend uploads directly to S3
 *
 * Usage:
 *   const { pickAndUpload, uploading, error, photoUrl, blurhash } = usePhotoUpload(itemId);
 */

import { useState, useCallback } from "react";
import { Alert, Linking } from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as FileSystem from "expo-file-system";
import { decode as atob } from "base-64";
import { collectorsApi } from "@/api/collectorsApi";
import type { ServerUploadResponse } from "@/api/collectorsApi";
import { useAuthContext } from "@/providers/useAuthContext";
import { logger } from "@/lib/logger";

/**
 * iOS presents each permission dialog only ONCE per install. After a denial the
 * request resolves instantly with `granted: false, canAskAgain: false` and no
 * dialog — so retrying the request is a no-op and the user is stuck with an
 * error string and no way to act on it. Route them to Settings instead, the
 * same way src/lib/calendar.ts does for calendar access.
 */
function promptOpenSettings(title: string, body: string) {
  Alert.alert(title, body, [
    { text: "Cancel", style: "cancel" },
    { text: "Open Settings", onPress: () => Linking.openSettings() },
  ]);
}

/**
 * Read a local file URI as raw bytes for an S3 PUT. RN's `fetch(uri).blob()`
 * body is unreliable against S3 (uploads empty / fails), which left every
 * item's image_url null when the server path fell back to presign. Reading the
 * file as base64 → Uint8Array and PUTting the bytes is the pattern proven in
 * src/utils/uploadImageS3.ts.
 */
async function readFileAsBytes(uri: string): Promise<Uint8Array> {
  const base64 = await FileSystem.readAsStringAsync(uri, { encoding: "base64" });
  const bin = atob(base64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

/** MIME type mapping from expo-image-picker type field */
const MIME_MAP: Record<string, string> = {
  image: "image/jpeg",
  // expo-image-picker doesn't provide granular type; we detect from URI
};

function getMimeType(uri: string): string {
  const lower = uri.toLowerCase();
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".webp")) return "image/webp";
  // Default to JPEG (most common from camera/gallery)
  return "image/jpeg";
}

export type PhotoUploadResult = {
  /** Pick a photo from camera or gallery and upload it */
  pickAndUpload: (source?: "camera" | "gallery") => Promise<string | null>;
  /** Upload an already-captured image by URI (e.g. handed off from QuickScan) */
  uploadFromUri: (uri: string, contentType?: string) => Promise<string | null>;
  /** Whether an upload is currently in progress */
  uploading: boolean;
  /** Last error message, if any */
  error: string | null;
  /** URL of the most recently uploaded photo */
  photoUrl: string | null;
  /** Blurhash string for the most recently uploaded photo (for placeholder rendering) */
  blurhash: string | null;
  /** Dimensions of the optimized image */
  dimensions: { width: number; height: number } | null;
  /** Clear the current error */
  clearError: () => void;
};

export function usePhotoUpload(itemId: string): PhotoUploadResult {
  const { user } = useAuthContext();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [blurhash, setBlurhash] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);

  const clearError = useCallback(() => setError(null), []);

  // Core upload: takes an image URI (from the picker OR handed off from
  // another flow like QuickScan) and pushes it through the server-side
  // optimized endpoint, falling back to the presigned-URL flow.
  const uploadFromUri = useCallback(
    async (uri: string, contentType?: string): Promise<string | null> => {
      if (!user?.id) {
        setError("You must be signed in to upload photos");
        return null;
      }

      setError(null);
      setUploading(true);

      const mime = contentType ?? getMimeType(uri);

      try {
        // 1. Try server-side optimized upload first
        try {
          const response: ServerUploadResponse = await collectorsApi.uploadPhoto(
            itemId,
            uri,
            mime,
          );

          setPhotoUrl(response.cdn_url);
          setBlurhash(response.blurhash);
          setDimensions({ width: response.width, height: response.height });

          logger.info(
            `[usePhotoUpload] Server-side upload complete: ${response.original_size} -> ${response.optimized_size} bytes`,
          );

          return response.cdn_url;
        } catch (serverErr: unknown) {
          logger.error(
            "[usePhotoUpload] Server-side upload failed, falling back to presigned URL:",
            serverErr instanceof Error ? serverErr.message : String(serverErr),
          );
        }

        // 2. Fallback: presigned URL flow
        const presignResponse = await collectorsApi.getPresignedUploadUrl(
          itemId,
          mime,
        );

        // PUT the raw file bytes (not a blob) — S3 signs `content-type`, so the
        // header must match the presigned content type exactly.
        const bytes = await readFileAsBytes(uri);
        const uploadResponse = await fetch(presignResponse.upload_url, {
          method: "PUT",
          headers: {
            "Content-Type": mime,
          },
          body: bytes as unknown as BodyInit,
        });

        if (!uploadResponse.ok) {
          const detail = await uploadResponse.text().catch(() => "");
          throw new Error(
            `S3 upload failed with status ${uploadResponse.status}${detail ? `: ${detail.slice(0, 120)}` : ""}`,
          );
        }

        setPhotoUrl(presignResponse.cdn_url);
        setBlurhash(null); // No blurhash from presigned flow
        setDimensions(null);
        return presignResponse.cdn_url;
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to upload photo";
        logger.error("[usePhotoUpload] Error:", message);
        setError(message);
        return null;
      } finally {
        setUploading(false);
      }
    },
    [itemId, user?.id],
  );

  const pickAndUpload = useCallback(
    async (source: "camera" | "gallery" = "gallery"): Promise<string | null> => {
      if (!user?.id) {
        setError("You must be signed in to upload photos");
        return null;
      }

      setError(null);

      // 1. Request permissions
      if (source === "camera") {
        const { status, canAskAgain } =
          await ImagePicker.requestCameraPermissionsAsync();
        if (status !== "granted") {
          setError("Camera permission is required to take photos");
          if (!canAskAgain) {
            promptOpenSettings(
              "Camera Access Is Off",
              "Camera access was turned off for Sparrow. Open Settings and switch Camera on to take photos.",
            );
          }
          return null;
        }
      } else {
        const { status, canAskAgain } =
          await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== "granted") {
          setError("Photo library permission is required to select photos");
          if (!canAskAgain) {
            promptOpenSettings(
              "Photo Access Is Off",
              "Photo library access was turned off for Sparrow. Open Settings and allow Photos to select images.",
            );
          }
          return null;
        }
      }

      // 2. Launch picker
      const pickerFn =
        source === "camera"
          ? ImagePicker.launchCameraAsync
          : ImagePicker.launchImageLibraryAsync;

      const result = await pickerFn({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.8,
        allowsEditing: true,
        aspect: [1, 1],
      });

      if (result.canceled || !result.assets?.length) {
        // User cancelled — not an error
        return null;
      }

      const asset = result.assets[0];
      // 3. Upload via the shared core
      return uploadFromUri(asset.uri, getMimeType(asset.uri));
    },
    [uploadFromUri, user?.id],
  );

  return { pickAndUpload, uploadFromUri, uploading, error, photoUrl, blurhash, dimensions, clearError };
}

export default usePhotoUpload;
