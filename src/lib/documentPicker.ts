/**
 * Typed wrapper around expo-document-picker.
 *
 * Normalises the return shape across Expo SDK versions so callers
 * never need `@ts-expect-error`.
 */
import * as DocumentPicker from "expo-document-picker";

export interface PickedDocument {
  uri: string;
  name: string;
  mimeType: string;
}

export type PickResult =
  | { canceled: true; document: null }
  | { canceled: false; document: PickedDocument };

/**
 * Open the document picker for the given MIME types.
 * Returns a normalised result regardless of the Expo SDK version.
 */
export async function pickDocument(
  mimeTypes: string[],
): Promise<PickResult> {
  const result = await DocumentPicker.getDocumentAsync({
    type: mimeTypes,
    copyToCacheDirectory: true,
  });

  if (!result) {
    return { canceled: true, document: null };
  }

  // SDK 49+ uses { canceled, assets }; older SDKs use { type, uri, name, mimeType }
  const raw = result as Record<string, unknown>;
  const isCanceled =
    raw.canceled === true || (raw.type != null && raw.type !== "success");

  if (isCanceled) {
    return { canceled: true, document: null };
  }

  const assets = raw.assets as Array<Record<string, unknown>> | undefined;
  const asset = assets && assets.length > 0 ? assets[0] : raw;

  const uri = asset.uri as string | undefined;
  if (!uri) {
    return { canceled: true, document: null };
  }

  return {
    canceled: false,
    document: {
      uri,
      name: (asset.name as string) || "collection.xlsx",
      mimeType: (asset.mimeType as string) || "application/octet-stream",
    },
  };
}
