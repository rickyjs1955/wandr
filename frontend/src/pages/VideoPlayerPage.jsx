/**
 * VideoPlayerPage
 *
 * Full page component for video playback with metadata and related actions.
 *
 * Route: /videos/:videoId
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { VideoPlayer } from '../components/VideoPlayer';
import { getVideo } from '../services/videoService';

export function VideoPlayerPage() {
  const { videoId } = useParams();
  const navigate = useNavigate();

  const [video, setVideo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchVideo();
  }, [videoId]);

  const fetchVideo = async () => {
    try {
      const videoData = await getVideo(videoId);
      setVideo(videoData);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch video:', err);
      setError(err.message || 'Failed to load video');
      setLoading(false);
    }
  };

  const handleBack = () => {
    // Navigate back to video list or mall/pin page
    if (video?.mall_id && video?.pin_id) {
      navigate(`/malls/${video.mall_id}/pins/${video.pin_id}/videos`);
    } else {
      navigate(-1); // Go back to previous page
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading video...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !video) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md text-center">
          <svg className="mx-auto h-12 w-12 text-red-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Video Not Found</h2>
          <p className="text-gray-600 mb-6">{error || 'The video you are looking for does not exist.'}</p>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={handleBack}
                className="text-gray-600 hover:text-gray-900"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{video.original_filename}</h1>
                <p className="text-sm text-gray-500 mt-1">
                  {video.pin_name} • {video.mall_name || 'Unknown Mall'}
                </p>
              </div>
            </div>

            {/* Processing Status Badge */}
            {video.processing_status && (
              <div>
                {video.processing_status === 'completed' && (
                  <span className="inline-flex px-3 py-1 text-sm font-semibold rounded-full bg-green-100 text-green-800">
                    ✓ Processed
                  </span>
                )}
                {video.processing_status === 'processing' && (
                  <span className="inline-flex px-3 py-1 text-sm font-semibold rounded-full bg-blue-100 text-blue-800">
                    ⚙️ Processing
                  </span>
                )}
                {video.processing_status === 'pending' && (
                  <span className="inline-flex px-3 py-1 text-sm font-semibold rounded-full bg-yellow-100 text-yellow-800">
                    ⏳ Pending
                  </span>
                )}
                {video.processing_status === 'failed' && (
                  <span className="inline-flex px-3 py-1 text-sm font-semibold rounded-full bg-red-100 text-red-800">
                    ✗ Failed
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Video Player */}
        {video.processing_status === 'completed' && video.has_proxy ? (
          <VideoPlayer
            videoId={videoId}
            streamType="proxy"
            videoMetadata={{
              filename: video.original_filename,
              duration_seconds: video.duration_seconds,
              uploaded_at: video.uploaded_at,
              recorded_at: video.recorded_at,
              operator_notes: video.operator_notes,
            }}
            showMetadata={true}
            onError={(err) => {
              console.error('Video player error:', err);
            }}
          />
        ) : (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            {video.processing_status === 'processing' && (
              <>
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Processing Video</h3>
                <p className="text-gray-600">
                  Your video is being processed. Proxy generation may take a few minutes.
                </p>
              </>
            )}
            {video.processing_status === 'pending' && (
              <>
                <svg className="mx-auto h-12 w-12 text-yellow-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Processing Queued</h3>
                <p className="text-gray-600">
                  Your video is in the processing queue. It will be processed shortly.
                </p>
              </>
            )}
            {video.processing_status === 'failed' && (
              <>
                <svg className="mx-auto h-12 w-12 text-red-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Processing Failed</h3>
                <p className="text-gray-600 mb-4">
                  {video.processing_error || 'An error occurred while processing this video.'}
                </p>
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Retry
                </button>
              </>
            )}
          </div>
        )}

        {/* Additional Info */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* File Information */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">File Information</h3>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm font-medium text-gray-500">File Size</dt>
                <dd className="text-sm text-gray-900 mt-1">
                  {(video.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
                </dd>
              </div>
              {video.width && video.height && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Resolution</dt>
                  <dd className="text-sm text-gray-900 mt-1">
                    {video.width} × {video.height}
                  </dd>
                </div>
              )}
              {video.fps && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Frame Rate</dt>
                  <dd className="text-sm text-gray-900 mt-1">{video.fps} fps</dd>
                </div>
              )}
              {video.codec && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Codec</dt>
                  <dd className="text-sm text-gray-900 mt-1">{video.codec}</dd>
                </div>
              )}
              {video.checksum_sha256 && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Checksum (SHA-256)</dt>
                  <dd className="text-xs text-gray-900 mt-1 font-mono break-all">
                    {video.checksum_sha256}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Processing Information */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Processing Information</h3>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm font-medium text-gray-500">Upload Status</dt>
                <dd className="text-sm text-gray-900 mt-1 capitalize">{video.upload_status || 'N/A'}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Processing Status</dt>
                <dd className="text-sm text-gray-900 mt-1 capitalize">{video.processing_status || 'N/A'}</dd>
              </div>
              {video.processing_started_at && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Processing Started</dt>
                  <dd className="text-sm text-gray-900 mt-1">
                    {new Date(video.processing_started_at).toLocaleString()}
                  </dd>
                </div>
              )}
              {video.processing_completed_at && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Processing Completed</dt>
                  <dd className="text-sm text-gray-900 mt-1">
                    {new Date(video.processing_completed_at).toLocaleString()}
                  </dd>
                </div>
              )}
              {video.has_proxy && (
                <div>
                  <dt className="text-sm font-medium text-gray-500">Proxy Available</dt>
                  <dd className="text-sm text-green-600 mt-1">✓ Yes</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}

export default VideoPlayerPage;
