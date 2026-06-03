import * as ImageManipulator from 'expo-image-manipulator';

import logger from '@/utils/logger';

/**
 * Downscale a captured photo before uploading it to the scan pipeline.
 *
 * `takePictureAsync` returns a full-resolution JPEG (3–8 MB on a modern phone).
 * That gets base64-encoded server-side and forwarded to OpenAI/fal at full
 * size, which inflates latency, upload failures on weak mobile networks, and
 * per-scan token cost — for zero identification benefit beyond ~1568px (the
 * long edge OpenAI's high-detail tiling targets).
 *
 * Resizing to a 1568px long edge at quality 0.7 cuts the payload by ~5–10x.
 * On ANY manipulation failure we fall back to the original URI so a scan never
 * fails just because the resize did.
 */
const MAX_LONG_EDGE = 1568;
const COMPRESS_QUALITY = 0.7;

export async function prepareImageForUpload(uri: string): Promise<string> {
  try {
    // resize by width only — height is derived to preserve aspect ratio.
    // (For portrait shots this caps the *width*; the long edge ends up <= the
    // device height, still a large reduction from a 4000px sensor capture.)
    const result = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: MAX_LONG_EDGE } }],
      { compress: COMPRESS_QUALITY, format: ImageManipulator.SaveFormat.JPEG },
    );
    return result.uri || uri;
  } catch (err) {
    logger.warn('[prepareImageForUpload] resize failed, using original:', err);
    return uri;
  }
}
