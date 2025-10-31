/**
 * Video service for managing video uploads, streaming, and management.
 *
 * Handles:
 * - Multipart upload initiation, completion, and abort
 * - Video listing with filters and pagination
 * - Video details retrieval
 * - Stream URL generation
 * - Video deletion
 * - Job status polling
 */

import api from './api';

/**
 * Initiate multipart upload for a video.
 *
 * @param {string} mallId - Mall UUID
 * @param {string} pinId - Camera pin UUID
 * @param {Object} data - Upload initiation data
 * @param {string} data.filename - Original filename (e.g., "entrance_a_2025_10_30_14_00.mp4")
 * @param {number} data.file_size_bytes - File size in bytes
 * @param {string} data.checksum_sha256 - SHA-256 checksum (hex)
 * @param {Object} data.metadata - Optional metadata
 * @param {string} data.metadata.recorded_at - ISO 8601 datetime of actual CCTV recording
 * @param {string} data.metadata.operator_notes - Optional notes about footage
 * @returns {Promise<Object>} - Upload initiation response
 * @returns {string} response.video_id - Video UUID
 * @returns {string} response.upload_id - S3 multipart upload ID
 * @returns {number} response.part_size_bytes - Size of each part (typically 10MB)
 * @returns {number} response.total_parts - Total number of parts
 * @returns {Array} response.presigned_urls - Array of {part_number, url}
 * @returns {string} response.expires_at - ISO 8601 datetime when presigned URLs expire
 *
 * @example
 * const response = await initiateUpload(mallId, pinId, {
 *   filename: 'entrance_a.mp4',
 *   file_size_bytes: 2147483648,
 *   checksum_sha256: 'a3f5b1c...',
 *   metadata: {
 *     recorded_at: '2025-10-30T14:30:00Z',
 *     operator_notes: 'Rush hour footage'
 *   }
 * });
 */
export async function initiateUpload(mallId, pinId, data) {
  const response = await api.post(
    `/malls/${mallId}/pins/${pinId}/uploads/initiate`,
    data
  );
  return response.data;
}

/**
 * Get presigned URLs for additional parts (if upload > 100 parts).
 *
 * @param {string} mallId - Mall UUID
 * @param {string} pinId - Camera pin UUID
 * @param {string} videoId - Video UUID
 * @param {number} startPart - Starting part number (1-indexed)
 * @param {number} endPart - Ending part number (inclusive)
 * @returns {Promise<Object>} - Presigned URLs response
 * @returns {Array} response.presigned_urls - Array of {part_number, url}
 *
 * @example
 * // Get URLs for parts 101-200
 * const response = await getPartUrls(mallId, pinId, videoId, 101, 200);
 */
export async function getPartUrls(mallId, pinId, videoId, startPart, endPart) {
  const response = await api.post(
    `/malls/${mallId}/pins/${pinId}/uploads/${videoId}/part-urls`,
    { start_part: startPart, end_part: endPart }
  );
  return response.data;
}

/**
 * Complete multipart upload after all parts are uploaded.
 *
 * @param {string} mallId - Mall UUID
 * @param {string} pinId - Camera pin UUID
 * @param {string} videoId - Video UUID
 * @param {Object} data - Completion data
 * @param {string} data.upload_id - S3 multipart upload ID
 * @param {Array} data.parts - Array of {part_number, etag}
 * @returns {Promise<Object>} - Completion response
 * @returns {string} response.video_id - Video UUID
 * @returns {string} response.upload_status - Upload status ('uploaded')
 * @returns {string} response.processing_status - Processing status ('pending')
 * @returns {string} response.job_id - Processing job UUID
 * @returns {string} response.uploaded_at - ISO 8601 datetime
 *
 * @example
 * const response = await completeUpload(mallId, pinId, videoId, {
 *   upload_id: 's3-multipart-upload-id',
 *   parts: [
 *     { part_number: 1, etag: '"abc123"' },
 *     { part_number: 2, etag: '"def456"' }
 *   ]
 * });
 */
export async function completeUpload(mallId, pinId, videoId, data) {
  const response = await api.post(
    `/malls/${mallId}/pins/${pinId}/uploads/${videoId}/complete`,
    data
  );
  return response.data;
}

/**
 * Abort multipart upload (cancel in-progress upload).
 *
 * @param {string} mallId - Mall UUID
 * @param {string} pinId - Camera pin UUID
 * @param {string} videoId - Video UUID
 * @returns {Promise<void>}
 *
 * @example
 * await abortUpload(mallId, pinId, videoId);
 */
export async function abortUpload(mallId, pinId, videoId) {
  await api.delete(`/malls/${mallId}/pins/${pinId}/uploads/${videoId}`);
}

/**
 * Get processing job status.
 *
 * @param {string} jobId - Processing job UUID
 * @returns {Promise<Object>} - Job status response
 * @returns {string} response.job_id - Job UUID
 * @returns {string} response.video_id - Video UUID
 * @returns {string} response.job_type - Job type (e.g., 'proxy_generation')
 * @returns {string} response.status - Job status ('pending', 'running', 'completed', 'failed')
 * @returns {string} response.started_at - ISO 8601 datetime (if started)
 * @returns {string} response.completed_at - ISO 8601 datetime (if completed)
 * @returns {string} response.error_message - Error message (if failed)
 *
 * @example
 * const job = await getJobStatus(jobId);
 * console.log('Job status:', job.status);
 */
export async function getJobStatus(jobId) {
  const response = await api.get(`/analysis/jobs/${jobId}`);
  return response.data;
}

/**
 * List videos for a camera pin with filters.
 *
 * @param {string} mallId - Mall UUID (optional, for filtering)
 * @param {string} pinId - Camera pin UUID (optional, for filtering)
 * @param {Object} filters - Filter options
 * @param {string} filters.processing_status - Filter by status
 * @param {boolean} filters.has_proxy - Filter by proxy existence
 * @param {string} filters.uploaded_after - ISO 8601 datetime
 * @param {string} filters.uploaded_before - ISO 8601 datetime
 * @param {number} filters.page - Page number (1-indexed)
 * @param {number} filters.page_size - Items per page (max 100)
 * @returns {Promise<Object>} - Video list response
 * @returns {Array} response.videos - Array of video items
 * @returns {number} response.total - Total count
 * @returns {number} response.page - Current page
 * @returns {number} response.page_size - Items per page
 * @returns {number} response.total_pages - Total pages
 *
 * @example
 * const response = await listVideos(mallId, pinId, {
 *   processing_status: 'completed',
 *   page: 1,
 *   page_size: 20
 * });
 */
export async function listVideos(mallId = null, pinId = null, filters = {}) {
  const params = new URLSearchParams();

  if (mallId) params.append('mall_id', mallId);
  if (pinId) params.append('pin_id', pinId);
  if (filters.processing_status) params.append('processing_status', filters.processing_status);
  if (filters.has_proxy !== undefined) params.append('has_proxy', filters.has_proxy);
  if (filters.uploaded_after) params.append('uploaded_after', filters.uploaded_after);
  if (filters.uploaded_before) params.append('uploaded_before', filters.uploaded_before);
  if (filters.page) params.append('page', filters.page);
  if (filters.page_size) params.append('page_size', filters.page_size);

  const response = await api.get(`/videos?${params.toString()}`);
  return response.data;
}

/**
 * Get video details.
 *
 * @param {string} videoId - Video UUID
 * @returns {Promise<Object>} - Video details
 *
 * @example
 * const video = await getVideo(videoId);
 * console.log('Duration:', video.duration_seconds, 'seconds');
 */
export async function getVideo(videoId) {
  const response = await api.get(`/videos/${videoId}`);
  return response.data;
}

/**
 * Get presigned URL for video streaming.
 *
 * @param {string} videoId - Video UUID
 * @param {string} streamType - Stream type ('proxy' or 'original')
 * @param {number} expiresMinutes - URL expiration time in minutes (default: 60)
 * @returns {Promise<Object>} - Stream URL response
 * @returns {string} response.url - Presigned streaming URL
 * @returns {string} response.expires_at - ISO 8601 datetime
 * @returns {number} response.file_size_bytes - File size
 * @returns {number} response.duration_seconds - Video duration
 *
 * @example
 * const { url } = await getStreamUrl(videoId, 'proxy');
 * videoElement.src = url;
 */
export async function getStreamUrl(videoId, streamType = 'proxy', expiresMinutes = 60) {
  const response = await api.get(
    `/videos/${videoId}/stream/${streamType}?expires_minutes=${expiresMinutes}`
  );
  return response.data;
}

/**
 * Get presigned URL for thumbnail.
 *
 * @param {string} videoId - Video UUID
 * @param {number} expiresMinutes - URL expiration time in minutes (default: 60)
 * @returns {Promise<Object>} - Thumbnail URL response
 * @returns {string} response.url - Presigned thumbnail URL
 * @returns {string} response.expires_at - ISO 8601 datetime
 *
 * @example
 * const { url } = await getThumbnailUrl(videoId);
 * imgElement.src = url;
 */
export async function getThumbnailUrl(videoId, expiresMinutes = 60) {
  const response = await api.get(
    `/videos/${videoId}/thumbnail?expires_minutes=${expiresMinutes}`
  );
  return response.data;
}

/**
 * Delete video and all associated files.
 *
 * @param {string} videoId - Video UUID
 * @param {boolean} deleteFiles - Delete files from storage (default: true)
 * @returns {Promise<Object>} - Deletion response
 * @returns {boolean} response.deleted - Deletion success
 * @returns {Array} response.files_deleted - List of deleted file paths
 *
 * @example
 * const response = await deleteVideo(videoId);
 * console.log('Deleted files:', response.files_deleted);
 */
export async function deleteVideo(videoId, deleteFiles = true) {
  const response = await api.delete(
    `/videos/${videoId}?delete_files=${deleteFiles}`
  );
  return response.data;
}

/**
 * Get upload status (for tracking incomplete uploads).
 *
 * @param {string} mallId - Mall UUID
 * @param {string} pinId - Camera pin UUID
 * @param {string} videoId - Video UUID
 * @returns {Promise<Object>} - Upload status response
 * @returns {string} response.video_id - Video UUID
 * @returns {string} response.upload_status - Upload status
 * @returns {string} response.upload_id - S3 multipart upload ID
 * @returns {number} response.parts_uploaded - Number of parts uploaded
 * @returns {number} response.total_parts - Total parts
 *
 * @example
 * const status = await getUploadStatus(mallId, pinId, videoId);
 * console.log(`Progress: ${status.parts_uploaded}/${status.total_parts}`);
 */
export async function getUploadStatus(mallId, pinId, videoId) {
  const response = await api.get(
    `/malls/${mallId}/pins/${pinId}/uploads/${videoId}/status`
  );
  return response.data;
}

export default {
  initiateUpload,
  getPartUrls,
  completeUpload,
  abortUpload,
  getJobStatus,
  listVideos,
  getVideo,
  getStreamUrl,
  getThumbnailUrl,
  deleteVideo,
  getUploadStatus,
};
