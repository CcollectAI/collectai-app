/**
 * Object Store Interface for S3/Hybrid Storage
 *
 * This module provides interfaces for the S3 data lake without embedding
 * AWS credentials in the mobile app. All S3 operations go through the backend.
 *
 * Design:
 * - Mobile app never has direct S3 access
 * - Backend provides presigned URLs for uploads
 * - Metadata pointers stored in Supabase Postgres
 *
 * S3 Layout (Dataset Lakehouse):
 * - s3://<bucket>/market_comps/dt=YYYY-MM-DD/category_id=.../source=.../*.parquet
 * - s3://<bucket>/price_comps/dt=YYYY-MM-DD/category_id=.../*.parquet
 * - s3://<bucket>/vision/images/dt=YYYY-MM-DD/user_id=.../*.jpg
 * - s3://<bucket>/vision/extracts/dt=YYYY-MM-DD/user_id=.../*.jsonl
 * - s3://<bucket>/embeddings/dt=YYYY-MM-DD/model=.../*.parquet
 */

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type ObjectStorePrefix =
  | 'market_comps'
  | 'price_comps'
  | 'vision/images'
  | 'vision/extracts'
  | 'embeddings'
  | 'training/raw'
  | 'training/processed';

import { logger } from '@/lib/logger';

export type ObjectMetadata = {
  objectKey: string;
  bucket: string;
  contentType: string;
  sizeBytes: number;
  hash?: string;  // MD5 or SHA256
  createdAt: string;
  tags?: Record<string, string>;
};

export type PresignedUploadRequest = {
  prefix: ObjectStorePrefix;
  filename: string;
  contentType: string;
  categoryId?: string;
  userId?: string;
  metadata?: Record<string, string>;
};

export type PresignedUploadResponse = {
  uploadUrl: string;
  objectKey: string;
  expiresAt: string;
  fields?: Record<string, string>;  // For POST-based presigned URLs
};

export type PresignedDownloadRequest = {
  objectKey: string;
  expiresInSeconds?: number;
};

export type PresignedDownloadResponse = {
  downloadUrl: string;
  expiresAt: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Object Store Interface
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Interface for object store operations.
 * Implementations should call backend APIs, never use AWS SDK directly in app.
 */
export interface ObjectStore {
  /**
   * Request a presigned URL for uploading an object.
   * The backend will generate the URL with proper credentials.
   */
  getPresignedUploadUrl(request: PresignedUploadRequest): Promise<PresignedUploadResponse>;

  /**
   * Request a presigned URL for downloading an object.
   */
  getPresignedDownloadUrl(request: PresignedDownloadRequest): Promise<PresignedDownloadResponse>;

  /**
   * Upload a file using a presigned URL.
   * This can be used client-side after getting the presigned URL.
   */
  uploadWithPresignedUrl(
    presignedUrl: string,
    data: Blob | ArrayBuffer,
    contentType: string,
    fields?: Record<string, string>
  ): Promise<void>;

  /**
   * Save metadata pointer in Postgres after successful upload.
   * This keeps the DB as the source of truth for what objects exist.
   */
  saveObjectPointer(metadata: ObjectMetadata): Promise<void>;

  /**
   * List object pointers from Postgres (not S3 directly).
   */
  listObjectPointers(options: {
    prefix?: ObjectStorePrefix;
    categoryId?: string;
    userId?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
  }): Promise<ObjectMetadata[]>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Path Builders (for backend use)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Build a partitioned S3 path for market comps.
 */
export function buildMarketCompsPath(options: {
  date: string;  // YYYY-MM-DD
  categoryId: string;
  source: string;
  filename: string;
}): string {
  return `market_comps/dt=${options.date}/category_id=${options.categoryId}/source=${options.source}/${options.filename}`;
}

/**
 * Build a partitioned S3 path for price comps.
 */
export function buildPriceCompsPath(options: {
  date: string;
  categoryId: string;
  filename: string;
}): string {
  return `price_comps/dt=${options.date}/category_id=${options.categoryId}/${options.filename}`;
}

/**
 * Build a partitioned S3 path for vision images.
 */
export function buildVisionImagePath(options: {
  date: string;
  userId: string;
  filename: string;
}): string {
  return `vision/images/dt=${options.date}/user_id=${options.userId}/${options.filename}`;
}

/**
 * Build a partitioned S3 path for vision extracts (OCR/metadata).
 */
export function buildVisionExtractPath(options: {
  date: string;
  userId: string;
  filename: string;
}): string {
  return `vision/extracts/dt=${options.date}/user_id=${options.userId}/${options.filename}`;
}

/**
 * Build a partitioned S3 path for embeddings.
 */
export function buildEmbeddingsPath(options: {
  date: string;
  model: string;
  filename: string;
}): string {
  return `embeddings/dt=${options.date}/model=${options.model}/${options.filename}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Mock Implementation (for development)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Mock object store for development.
 * Returns fake presigned URLs and stores pointers in memory.
 */
export class MockObjectStore implements ObjectStore {
  private pointers: ObjectMetadata[] = [];

  async getPresignedUploadUrl(request: PresignedUploadRequest): Promise<PresignedUploadResponse> {
    const date = new Date().toISOString().split('T')[0];
    const objectKey = `${request.prefix}/dt=${date}/${request.categoryId ? `category_id=${request.categoryId}/` : ''}${request.userId ? `user_id=${request.userId}/` : ''}${request.filename}`;

    return {
      uploadUrl: `https://mock-bucket.s3.amazonaws.com/${objectKey}?X-Amz-Algorithm=mock`,
      objectKey,
      expiresAt: new Date(Date.now() + 3600 * 1000).toISOString(),
    };
  }

  async getPresignedDownloadUrl(request: PresignedDownloadRequest): Promise<PresignedDownloadResponse> {
    return {
      downloadUrl: `https://mock-bucket.s3.amazonaws.com/${request.objectKey}?X-Amz-Algorithm=mock`,
      expiresAt: new Date(Date.now() + (request.expiresInSeconds ?? 3600) * 1000).toISOString(),
    };
  }

  async uploadWithPresignedUrl(
    _presignedUrl: string,
    _data: Blob | ArrayBuffer,
    _contentType: string,
    _fields?: Record<string, string>
  ): Promise<void> {
    // Mock: just pretend the upload succeeded
    logger.info('[MockObjectStore] Upload simulated');
  }

  async saveObjectPointer(metadata: ObjectMetadata): Promise<void> {
    this.pointers.push(metadata);
    logger.info('[MockObjectStore] Saved pointer:', metadata.objectKey);
  }

  async listObjectPointers(options: {
    prefix?: ObjectStorePrefix;
    categoryId?: string;
    userId?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
  }): Promise<ObjectMetadata[]> {
    let filtered = [...this.pointers];

    if (options.prefix) {
      filtered = filtered.filter((p) => p.objectKey.startsWith(options.prefix!));
    }
    if (options.categoryId) {
      filtered = filtered.filter((p) => p.objectKey.includes(`category_id=${options.categoryId}`));
    }
    if (options.userId) {
      filtered = filtered.filter((p) => p.objectKey.includes(`user_id=${options.userId}`));
    }
    if (options.limit) {
      filtered = filtered.slice(0, options.limit);
    }

    return filtered;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Factory
// ─────────────────────────────────────────────────────────────────────────────

let _objectStore: ObjectStore | null = null;

/**
 * Get the object store instance.
 * Returns mock by default; real implementation requires backend setup.
 */
export function getObjectStore(): ObjectStore {
  if (!_objectStore) {
    // Uses mock store until S3 presigned URL backend is configured
    _objectStore = new MockObjectStore();
  }
  return _objectStore;
}

/**
 * Set a custom object store implementation (for testing or real backend).
 */
export function setObjectStore(store: ObjectStore): void {
  _objectStore = store;
}
