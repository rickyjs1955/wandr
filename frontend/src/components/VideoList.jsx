/**
 * VideoList Component
 *
 * Displays a paginated list of videos with filtering and sorting.
 *
 * Features:
 * - Table/grid view toggle
 * - Status filtering (pending, processing, completed, failed)
 * - Date range filtering
 * - Pagination
 * - Delete confirmation
 * - Thumbnail previews
 * - Click to navigate to video player
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { listVideos, deleteVideo } from '../services/videoService';
import { useThumbnailUrl } from '../hooks/useSignedUrl';
import { formatBytes } from '../utils/multipartUpload';

/**
 * VideoList component for browsing videos.
 *
 * @param {Object} props - Component props
 * @param {string} props.mallId - Mall UUID (optional, for filtering)
 * @param {string} props.pinId - Camera pin UUID (optional, for filtering)
 * @param {boolean} props.showUploadButton - Show upload button (default: true)
 * @param {Function} props.onUploadClick - Upload button click handler
 * @param {Function} props.onVideoClick - Video click handler (videoId) => void
 * @param {boolean} props.enableDelete - Enable delete functionality (default: true)
 */
export function VideoList({
  mallId = null,
  pinId = null,
  showUploadButton = true,
  onUploadClick,
  onVideoClick,
  enableDelete = true,
}) {
  const navigate = useNavigate();

  // Video list state
  const [videos, setVideos] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter state
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  // UI state
  const [viewMode, setViewMode] = useState('table'); // 'table' or 'grid'
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Fetch videos
  useEffect(() => {
    fetchVideos();
  }, [mallId, pinId, statusFilter, dateFrom, dateTo, page]);

  const fetchVideos = async () => {
    setLoading(true);
    setError(null);

    try {
      const filters = {
        page,
        page_size: pageSize,
      };

      if (statusFilter) filters.processing_status = statusFilter;
      if (dateFrom) filters.uploaded_after = new Date(dateFrom).toISOString();
      if (dateTo) filters.uploaded_before = new Date(dateTo).toISOString();

      const response = await listVideos(mallId, pinId, filters);

      setVideos(response.videos);
      setTotal(response.total);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch videos:', err);
      setError(err.message || 'Failed to load videos');
      setLoading(false);
    }
  };

  // Handle video click
  const handleVideoClick = (videoId) => {
    if (onVideoClick) {
      onVideoClick(videoId);
    } else {
      navigate(`/videos/${videoId}`);
    }
  };

  // Handle delete
  const handleDeleteClick = (videoId, e) => {
    e.stopPropagation(); // Prevent row click
    setDeleteConfirmId(videoId);
  };

  const confirmDelete = async () => {
    if (!deleteConfirmId) return;

    setDeleting(true);
    try {
      await deleteVideo(deleteConfirmId);
      setDeleteConfirmId(null);
      setDeleting(false);
      // Refresh list
      fetchVideos();
    } catch (err) {
      console.error('Failed to delete video:', err);
      alert('Failed to delete video: ' + err.message);
      setDeleting(false);
    }
  };

  const cancelDelete = () => {
    setDeleteConfirmId(null);
  };

  // Pagination
  const totalPages = Math.ceil(total / pageSize);
  const canGoPrev = page > 1;
  const canGoNext = page < totalPages;

  // Format time
  const formatTime = (seconds) => {
    if (!seconds) return 'N/A';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Status badge
  const StatusBadge = ({ status }) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800',
      processing: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };

    return (
      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
        {status}
      </span>
    );
  };

  // Thumbnail component with lazy loading
  const VideoThumbnail = ({ videoId }) => {
    const { url, loading, error } = useThumbnailUrl(videoId);

    if (loading || error) {
      return (
        <div className="w-full h-full bg-gray-200 flex items-center justify-center">
          <svg className="w-8 h-8 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clipRule="evenodd" />
          </svg>
        </div>
      );
    }

    return <img src={url} alt="Video thumbnail" className="w-full h-full object-cover" />;
  };

  // Loading state
  if (loading && videos.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading videos...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && videos.length === 0) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-700 font-medium">Failed to load videos</p>
        <p className="text-red-600 text-sm mt-2">{error}</p>
        <button
          onClick={fetchVideos}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Videos</h2>
          <p className="text-sm text-gray-600 mt-1">{total} total videos</p>
        </div>

        <div className="flex gap-2">
          {/* View Toggle */}
          <div className="inline-flex rounded-md shadow-sm">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-2 text-sm font-medium rounded-l-md border ${
                viewMode === 'table'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              Table
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`px-3 py-2 text-sm font-medium rounded-r-md border-t border-r border-b ${
                viewMode === 'grid'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              Grid
            </button>
          </div>

          {/* Upload Button */}
          {showUploadButton && (
            <button
              onClick={onUploadClick}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
            >
              Upload Video
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="processing">Processing</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Date From */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              From Date
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Date To */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              To Date
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Clear Filters */}
        {(statusFilter || dateFrom || dateTo) && (
          <button
            onClick={() => {
              setStatusFilter('');
              setDateFrom('');
              setDateTo('');
              setPage(1);
            }}
            className="mt-3 text-sm text-blue-600 hover:text-blue-700"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Video List - Table View */}
      {viewMode === 'table' && videos.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Thumbnail
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Filename
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Uploaded
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                {enableDelete && (
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {videos.map((video) => (
                <tr
                  key={video.id}
                  onClick={() => handleVideoClick(video.id)}
                  className="hover:bg-gray-50 cursor-pointer transition"
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="w-16 h-12 rounded overflow-hidden">
                      {video.has_thumbnail ? (
                        <VideoThumbnail videoId={video.id} />
                      ) : (
                        <div className="w-full h-full bg-gray-200 flex items-center justify-center">
                          <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900">{video.original_filename}</div>
                    <div className="text-sm text-gray-500">{formatBytes(video.file_size_bytes)}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatTime(video.duration_seconds)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(video.uploaded_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <StatusBadge status={video.processing_status} />
                  </td>
                  {enableDelete && (
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={(e) => handleDeleteClick(video.id, e)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Video List - Grid View */}
      {viewMode === 'grid' && videos.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {videos.map((video) => (
            <div
              key={video.id}
              onClick={() => handleVideoClick(video.id)}
              className="bg-white rounded-lg shadow overflow-hidden hover:shadow-lg transition cursor-pointer"
            >
              {/* Thumbnail */}
              <div className="aspect-video bg-gray-200">
                {video.has_thumbnail ? (
                  <VideoThumbnail videoId={video.id} />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <svg className="w-12 h-12 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="p-4">
                <h3 className="text-sm font-medium text-gray-900 truncate">{video.original_filename}</h3>
                <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                  <span>{formatTime(video.duration_seconds)}</span>
                  <span>{formatBytes(video.file_size_bytes)}</span>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <StatusBadge status={video.processing_status} />
                  {enableDelete && (
                    <button
                      onClick={(e) => handleDeleteClick(video.id, e)}
                      className="text-red-600 hover:text-red-900 text-xs"
                    >
                      Delete
                    </button>
                  )}
                </div>
                <p className="mt-2 text-xs text-gray-500">
                  {new Date(video.uploaded_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {videos.length === 0 && !loading && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No videos found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {statusFilter || dateFrom || dateTo ? 'Try adjusting your filters' : 'Get started by uploading a video'}
          </p>
          {showUploadButton && !statusFilter && !dateFrom && !dateTo && (
            <button
              onClick={onUploadClick}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Upload Your First Video
            </button>
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between bg-white px-4 py-3 rounded-lg shadow">
          <div className="text-sm text-gray-700">
            Showing <span className="font-medium">{(page - 1) * pageSize + 1}</span> to{' '}
            <span className="font-medium">{Math.min(page * pageSize, total)}</span> of{' '}
            <span className="font-medium">{total}</span> results
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(page - 1)}
              disabled={!canGoPrev}
              className="px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={!canGoNext}
              className="px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Confirm Deletion</h3>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to delete this video? This action cannot be undone. All associated files (original, proxy, thumbnail) will be permanently deleted.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={cancelDelete}
                disabled={deleting}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default VideoList;
