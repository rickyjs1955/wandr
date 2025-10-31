/**
 * Multipart upload utility for large video files (up to 2GB).
 *
 * Handles:
 * - File chunking and sequential part upload
 * - Progress tracking
 * - Error handling and retry logic
 * - S3 presigned URL uploads (frontend → S3 direct)
 * - Checksum calculation
 *
 * Architecture:
 * 1. Frontend computes SHA-256 checksum
 * 2. Backend initiates S3 multipart upload, returns presigned URLs
 * 3. Frontend uploads parts directly to S3 (no API worker pinning)
 * 4. Frontend completes upload via backend, which triggers processing
 */

import { computeSHA256 } from './checksum';
import {
  initiateUpload,
  getPartUrls,
  completeUpload,
  abortUpload,
} from '../services/videoService';

/**
 * Upload video using multipart upload.
 *
 * @param {string} mallId - Mall UUID
 * @param {string} pinId - Camera pin UUID
 * @param {File} file - Video file to upload
 * @param {Object} metadata - Optional metadata
 * @param {string} metadata.recorded_at - ISO 8601 datetime of recording
 * @param {string} metadata.operator_notes - Notes about the footage
 * @param {Function} onProgress - Progress callback
 * @param {Function} onProgress.checksumProgress - (percent) => void
 * @param {Function} onProgress.uploadProgress - (percent, bytesUploaded, totalBytes) => void
 * @param {AbortSignal} signal - Optional AbortController signal for cancellation
 * @returns {Promise<string>} - Uploaded video ID
 *
 * @throws {Error} - If upload fails
 *
 * @example
 * const videoId = await uploadVideoMultipart(
 *   mallId,
 *   pinId,
 *   file,
 *   {
 *     recorded_at: '2025-10-30T14:00:00Z',
 *     operator_notes: 'Rush hour footage'
 *   },
 *   {
 *     checksumProgress: (percent) => console.log(`Checksum: ${percent}%`),
 *     uploadProgress: (percent) => console.log(`Upload: ${percent}%`)
 *   }
 * );
 */
export async function uploadVideoMultipart(
  mallId,
  pinId,
  file,
  metadata = {},
  onProgress = {},
  signal = null
) {
  const {
    checksumProgress = () => {},
    uploadProgress = () => {},
  } = onProgress;

  let videoId = null;
  let uploadId = null;

  try {
    // Step 1: Compute SHA-256 checksum
    checksumProgress(0);
    const checksum = await computeSHA256(file, (processed, total) => {
      const percent = Math.round((processed / total) * 100);
      checksumProgress(percent);
    });
    checksumProgress(100);

    // Check if aborted
    if (signal?.aborted) {
      throw new Error('Upload cancelled by user');
    }

    // Step 2: Initiate multipart upload
    const initResponse = await initiateUpload(mallId, pinId, {
      filename: file.name,
      file_size_bytes: file.size,
      checksum_sha256: checksum,
      metadata: metadata || undefined,
    });

    videoId = initResponse.video_id;
    uploadId = initResponse.upload_id;
    const partSize = initResponse.part_size_bytes;
    const totalParts = initResponse.total_parts;
    let presignedUrls = initResponse.presigned_urls;

    // Check if duplicate (backend returns existing video_id)
    if (initResponse.duplicate) {
      console.log('Duplicate video detected, skipping upload');
      return videoId;
    }

    // Step 3: Upload parts directly to S3
    const completedParts = [];
    let bytesUploaded = 0;

    for (let partNumber = 1; partNumber <= totalParts; partNumber++) {
      // Check if aborted
      if (signal?.aborted) {
        throw new Error('Upload cancelled by user');
      }

      // Fetch more presigned URLs if needed (backend returns first 100)
      if (partNumber > presignedUrls.length) {
        const startPart = presignedUrls.length + 1;
        const endPart = Math.min(startPart + 99, totalParts); // Fetch next 100
        const moreUrls = await getPartUrls(mallId, pinId, videoId, startPart, endPart);
        presignedUrls = presignedUrls.concat(moreUrls.presigned_urls);
      }

      // Get presigned URL for this part
      const urlInfo = presignedUrls.find(u => u.part_number === partNumber);
      if (!urlInfo) {
        throw new Error(`No presigned URL for part ${partNumber}`);
      }

      // Extract part from file
      const start = (partNumber - 1) * partSize;
      const end = Math.min(start + partSize, file.size);
      const chunk = file.slice(start, end);

      // Upload part to S3 with retry logic
      const etag = await uploadPartWithRetry(
        urlInfo.url,
        chunk,
        partNumber,
        3, // max retries
        signal
      );

      completedParts.push({
        part_number: partNumber,
        etag: etag,
      });

      // Update progress
      bytesUploaded += chunk.size;
      const percent = Math.round((bytesUploaded / file.size) * 100);
      uploadProgress(percent, bytesUploaded, file.size);
    }

    // Check if aborted before completion
    if (signal?.aborted) {
      throw new Error('Upload cancelled by user');
    }

    // Step 4: Complete multipart upload
    const completeResponse = await completeUpload(mallId, pinId, videoId, {
      upload_id: uploadId,
      parts: completedParts,
    });

    // Return both video_id and processing_job_id
    return {
      video_id: completeResponse.video_id,
      job_id: completeResponse.processing_job_id,
    };

  } catch (error) {
    // Abort upload on error
    if (videoId && uploadId) {
      try {
        await abortUpload(mallId, pinId, videoId);
      } catch (abortError) {
        console.error('Failed to abort upload:', abortError);
      }
    }

    throw error;
  }
}

/**
 * Upload a single part to S3 with retry logic.
 *
 * @param {string} presignedUrl - S3 presigned PUT URL
 * @param {Blob} chunk - File chunk to upload
 * @param {number} partNumber - Part number (for logging)
 * @param {number} maxRetries - Maximum retry attempts (default: 3)
 * @param {AbortSignal} signal - Optional abort signal
 * @returns {Promise<string>} - ETag from S3 response
 *
 * @throws {Error} - If upload fails after all retries
 */
async function uploadPartWithRetry(presignedUrl, chunk, partNumber, maxRetries = 3, signal = null) {
  let lastError = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      // Check if aborted
      if (signal?.aborted) {
        throw new Error('Upload cancelled by user');
      }

      // Upload to S3
      const response = await fetch(presignedUrl, {
        method: 'PUT',
        body: chunk,
        headers: {
          'Content-Type': 'video/mp4',
        },
        signal: signal,
      });

      if (!response.ok) {
        throw new Error(`S3 upload failed: ${response.status} ${response.statusText}`);
      }

      // Extract ETag from response headers
      const etag = response.headers.get('ETag');
      if (!etag) {
        throw new Error('S3 response missing ETag header');
      }

      // Success
      return etag;

    } catch (error) {
      lastError = error;

      // Don't retry if aborted
      if (signal?.aborted || error.name === 'AbortError') {
        throw error;
      }

      // Log retry attempt
      console.warn(
        `Part ${partNumber} upload failed (attempt ${attempt}/${maxRetries}):`,
        error.message
      );

      // Wait before retry (exponential backoff: 1s, 2s, 4s)
      if (attempt < maxRetries) {
        const delay = Math.pow(2, attempt - 1) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  // All retries failed
  throw new Error(
    `Part ${partNumber} upload failed after ${maxRetries} attempts: ${lastError.message}`
  );
}

/**
 * Validate video file before upload.
 *
 * @param {File} file - File to validate
 * @param {number} maxSizeBytes - Maximum file size (default: 2GB)
 * @returns {Object} - Validation result
 * @returns {boolean} result.valid - Whether file is valid
 * @returns {string} result.error - Error message if invalid
 *
 * @example
 * const validation = validateVideoFile(file);
 * if (!validation.valid) {
 *   alert(validation.error);
 *   return;
 * }
 */
export function validateVideoFile(file, maxSizeBytes = 2 * 1024 * 1024 * 1024) {
  // Check if file exists
  if (!file) {
    return { valid: false, error: 'No file selected' };
  }

  // Check file extension
  const extension = file.name.split('.').pop().toLowerCase();
  if (extension !== 'mp4') {
    return {
      valid: false,
      error: 'Only MP4 files are supported',
    };
  }

  // Check MIME type
  if (file.type && file.type !== 'video/mp4') {
    return {
      valid: false,
      error: `Invalid MIME type: ${file.type}. Expected video/mp4`,
    };
  }

  // Check file size
  if (file.size > maxSizeBytes) {
    const maxSizeGB = (maxSizeBytes / (1024 * 1024 * 1024)).toFixed(1);
    const fileSizeGB = (file.size / (1024 * 1024 * 1024)).toFixed(2);
    return {
      valid: false,
      error: `File too large: ${fileSizeGB}GB. Maximum size: ${maxSizeGB}GB`,
    };
  }

  // Check file size is not zero
  if (file.size === 0) {
    return {
      valid: false,
      error: 'File is empty (0 bytes)',
    };
  }

  return { valid: true, error: null };
}

/**
 * Format bytes to human-readable string.
 *
 * @param {number} bytes - Bytes to format
 * @param {number} decimals - Decimal places (default: 2)
 * @returns {string} - Formatted string (e.g., "1.23 GB")
 *
 * @example
 * formatBytes(1073741824) // "1.00 GB"
 * formatBytes(2147483648, 1) // "2.0 GB"
 */
export function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export default {
  uploadVideoMultipart,
  validateVideoFile,
  formatBytes,
};
