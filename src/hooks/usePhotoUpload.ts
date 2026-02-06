/**
 * Hook for uploading user photos to S3 via presigned URLs.
 *
 * Flow:
 * 1. User picks a photo from camera or gallery (via expo-image-picker)
 * 2. Frontend calls backend /photos/presign-upload to get a presigned S3 PUT URL
 * 3. Frontend uploads the image directly to S3 (no proxy through backend)
 * 4. Returns the CDN/S3 URL for display
 *
 * Usage:
 *   const { pickAndUpload, uploading, error, photoUrl } = usePhotoUpload(itemId);
 */

import { useState, useCallback } from "react";
import * as ImagePicker from "expo-image-picker";
import { Alert, Platform } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";
import { useSession } from "./useSession";

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
  /** Pick a photo from camera or gallery and upload it to S3 */
  pickAndUpload: (source?: "camera" | "gallery") => Promise<string | null>;
  /** Whether an upload is currently in progress */
  uploading: boolean;
  /** Last error message, if any */
  error: string | null;
  /** URL of the most recently uploaded photo */
  photoUrl: string | null;
  /** Clear the current error */
  clearError: () => void;
};

export function usePhotoUpload(itemId: string): PhotoUploadResult {
  const { user } = useSession();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const pickAndUpload = useCallback(
    async (source: "camera" | "gallery" = "gallery"): Promise<string | null> => {
      if (!user?.id) {
        setError("You must be signed in to upload photos");
        return null;
      }

      setError(null);
      setUploading(true);

      try {
        // 1. Request permissions
        if (source === "camera") {
          const { status } = await ImagePicker.requestCameraPermissionsAsync();
          if (status !== "granted") {
            setError("Camera permission is required to take photos");
            return null;
          }
        } else {
          const { status } =
            await ImagePicker.requestMediaLibraryPermissionsAsync();
          if (status !== "granted") {
            setError("Photo library permission is required to select photos");
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
        const uri = asset.uri;
        const contentType = getMimeType(uri);

        // 3. Get presigned URL from backend
        const presignResponse = await collectorsApi.getPresignedUploadUrl(
          itemId,
          contentType,
          user.id,
        );

        // 4. Upload directly to S3
        const imageResponse = await fetch(uri);
        const blob = await imageResponse.blob();

        const uploadResponse = await fetch(presignResponse.upload_url, {
          method: "PUT",
          headers: {
            "Content-Type": contentType,
          },
          body: blob,
        });

        if (!uploadResponse.ok) {
          throw new Error(
            `S3 upload failed with status ${uploadResponse.status}`,
          );
        }

        // 5. Return the CDN URL
        setPhotoUrl(presignResponse.cdn_url);
        return presignResponse.cdn_url;
      } catch (err: any) {
        const message = err?.message || "Failed to upload photo";
        console.error("[usePhotoUpload] Error:", message);
        setError(message);
        return null;
      } finally {
        setUploading(false);
      }
    },
    [itemId, user?.id],
  );

  return { pickAndUpload, uploading, error, photoUrl, clearError };
}

export default usePhotoUpload;
