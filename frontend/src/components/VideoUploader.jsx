/**
 * VideoUploader Component
 *
 * Provides a complete video upload interface with:
 * - File selection via drag-and-drop or file picker
 * - File validation (MP4 only, max 2GB)
 * - Metadata form (recorded_at, operator_notes)
 * - Checksum calculation progress
 * - Upload progress tracking
 * - Processing status polling
 * - Error handling and retry
 * - Cancellation support
 */

import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadVideoMultipart, validateVideoFile, formatBytes } from '../utils/multipartUpload';
import { useJobStatus } from '../hooks/useJobStatus';

/**
 * VideoUploader component for multipart video uploads.
 *
 * @param {Object} props - Component props
 * @param {string} props.mallId - Mall UUID
 * @param {string} props.pinId - Camera pin UUID
 * @param {Function} props.onUploadComplete - Callback when upload succeeds (videoId) => void
 * @param {Function} props.onUploadError - Callback when upload fails (error) => void
 * @param {Function} props.onCancel - Callback when upload is cancelled
 * @param {number} props.maxSizeGB - Maximum file size in GB (default: 2)
 */
export function VideoUploader({
  mallId,
  pinId,
  onUploadComplete,
  onUploadError,
  onCancel,
  maxSizeGB = 2,
}) {
  // File state
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  // Form state
  const [recordedAt, setRecordedAt] = useState('');
  const [operatorNotes, setOperatorNotes] = useState('');

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [checksumProgress, setChecksumProgress] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [bytesUploaded, setBytesUploaded] = useState(0);
  const [error, setError] = useState(null);

  // Processing state
  const [videoId, setVideoId] = useState(null);
  const [jobId, setJobId] = useState(null);

  // Refs
  const fileInputRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Router navigation
  const navigate = useNavigate();

  // Poll job status when jobId is set
  const { status: jobStatus, error: jobError } = useJobStatus(jobId, {
    enabled: !!jobId,
  });

  // Handle file selection
  const handleFileSelect = (selectedFile) => {
    // Reset state
    setError(null);
    setChecksumProgress(0);
    setUploadProgress(0);
    setBytesUploaded(0);

    // Validate file
    const validation = validateVideoFile(selectedFile, maxSizeGB * 1024 * 1024 * 1024);
    if (!validation.valid) {
      setError(validation.error);
      return;
    }

    setFile(selectedFile);
  };

  // Handle drag events
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  // Handle upload
  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    setUploading(true);
    setError(null);
    setChecksumProgress(0);
    setUploadProgress(0);

    try {
      // Prepare metadata
      const metadata = {
        recorded_at: recordedAt || undefined,
        operator_notes: operatorNotes || undefined,
      };

      // Upload video
      const uploadResult = await uploadVideoMultipart(
        mallId,
        pinId,
        file,
        metadata,
        {
          checksumProgress: (percent) => setChecksumProgress(percent),
          uploadProgress: (percent, bytes, total) => {
            setUploadProgress(percent);
            setBytesUploaded(bytes);
          },
        },
        abortControllerRef.current.signal
      );

      // Extract video_id and job_id from response
      setVideoId(uploadResult.video_id);
      setJobId(uploadResult.job_id);

      // Processing will be triggered automatically by backend
      // Job status polling will start now that jobId is set (via useJobStatus hook)
      setUploading(false);

      // Notify parent component
      if (onUploadComplete) {
        onUploadComplete(uploadResult.video_id);
      }

    } catch (err) {
      setUploading(false);
      setError(err.message || 'Upload failed');
      console.error('Upload error:', err);

      if (onUploadError) {
        onUploadError(err);
      }
    }
  };

  // Handle cancel
  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    setUploading(false);
    setFile(null);
    setError(null);
    setChecksumProgress(0);
    setUploadProgress(0);

    if (onCancel) {
      onCancel();
    }
  };

  // Render upload status
  const renderStatus = () => {
    if (error) {
      return (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700 font-medium">❌ Error</p>
          <p className="text-red-600 text-sm mt-1">{error}</p>
        </div>
      );
    }

    if (uploading) {
      if (checksumProgress < 100) {
        return (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-blue-700 font-medium">Calculating checksum...</p>
            <div className="mt-2 w-full bg-blue-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${checksumProgress}%` }}
              />
            </div>
            <p className="text-blue-600 text-sm mt-1">{checksumProgress}%</p>
          </div>
        );
      }

      if (uploadProgress < 100) {
        return (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-blue-700 font-medium">Uploading video...</p>
            <div className="mt-2 w-full bg-blue-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-blue-600 text-sm mt-1">
              {uploadProgress}% ({formatBytes(bytesUploaded)} / {formatBytes(file?.size || 0)})
            </p>
          </div>
        );
      }
    }

    if (videoId) {
      if (jobStatus === 'pending') {
        return (
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-yellow-700 font-medium">⏳ Processing queued...</p>
            <p className="text-yellow-600 text-sm mt-1">
              Your video is in the processing queue. This may take a few minutes.
            </p>
          </div>
        );
      }

      if (jobStatus === 'running') {
        return (
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-yellow-700 font-medium">⚙️ Processing video...</p>
            <p className="text-yellow-600 text-sm mt-1">
              Generating proxy video and thumbnail. This may take a few minutes.
            </p>
          </div>
        );
      }

      if (jobStatus === 'completed') {
        return (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-700 font-medium">✅ Processing complete!</p>
            <p className="text-green-600 text-sm mt-1">
              Your video has been uploaded and processed successfully.
            </p>
            <button
              onClick={() => navigate(`/videos/${videoId}`)}
              className="mt-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              View Video
            </button>
          </div>
        );
      }

      if (jobStatus === 'failed' || jobError) {
        return (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700 font-medium">❌ Processing failed</p>
            <p className="text-red-600 text-sm mt-1">
              {jobError || 'Video processing failed. Please try again.'}
            </p>
          </div>
        );
      }

      // Upload complete, waiting for processing to start
      return (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-700 font-medium">✅ Upload complete!</p>
          <p className="text-green-600 text-sm mt-1">
            Processing will begin shortly...
          </p>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Upload Video</h2>

      {/* File Drop Zone */}
      <div
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 bg-gray-50 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,.mp4"
          onChange={handleFileInputChange}
          className="hidden"
          disabled={uploading}
        />

        {!file ? (
          <>
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="mt-2 text-sm text-gray-600">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="font-medium text-blue-600 hover:text-blue-500"
              >
                Click to select
              </button>
              {' '}or drag and drop
            </p>
            <p className="text-xs text-gray-500 mt-1">
              MP4 files only, up to {maxSizeGB}GB
            </p>
          </>
        ) : (
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Selected file:</p>
            <p className="text-base text-gray-900">{file.name}</p>
            <p className="text-sm text-gray-500">{formatBytes(file.size)}</p>
            {!uploading && (
              <button
                onClick={() => setFile(null)}
                className="mt-2 text-sm text-red-600 hover:text-red-700"
              >
                Remove
              </button>
            )}
          </div>
        )}
      </div>

      {/* Metadata Form */}
      {file && !videoId && (
        <div className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Recorded At (Optional)
            </label>
            <input
              type="datetime-local"
              value={recordedAt}
              onChange={(e) => setRecordedAt(e.target.value)}
              disabled={uploading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
            />
            <p className="mt-1 text-xs text-gray-500">
              When was this footage recorded? (Not when it was uploaded)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Operator Notes (Optional)
            </label>
            <textarea
              value={operatorNotes}
              onChange={(e) => setOperatorNotes(e.target.value)}
              disabled={uploading}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
              placeholder="Add any notes about this footage (e.g., 'Rush hour', 'Incident at 14:30', etc.)"
            />
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {file && !videoId && (
        <div className="mt-6 flex gap-3">
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
          >
            {uploading ? 'Uploading...' : 'Upload Video'}
          </button>
          {uploading && (
            <button
              onClick={handleCancel}
              className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      {/* Status Display */}
      {renderStatus()}
    </div>
  );
}

export default VideoUploader;
