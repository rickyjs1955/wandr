/**
 * VideoListPage
 *
 * Full page component for browsing and managing videos.
 *
 * Routes:
 * - /videos (all videos)
 * - /malls/:mallId/videos (mall-specific)
 * - /malls/:mallId/pins/:pinId/videos (pin-specific)
 */

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { VideoList } from '../components/VideoList';
import { VideoUploader } from '../components/VideoUploader';

export function VideoListPage() {
  const { mallId, pinId } = useParams();
  const navigate = useNavigate();

  const [showUploader, setShowUploader] = React.useState(false);

  const handleUploadClick = () => {
    if (mallId && pinId) {
      setShowUploader(true);
    } else {
      // If no mall/pin context, navigate to mall selection
      navigate('/malls');
    }
  };

  const handleUploadComplete = (videoId) => {
    setShowUploader(false);
    // Navigate to video player
    navigate(`/videos/${videoId}`);
  };

  const handleUploadCancel = () => {
    setShowUploader(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {pinId ? 'Camera Videos' : mallId ? 'Mall Videos' : 'All Videos'}
              </h1>
              <p className="mt-2 text-sm text-gray-600">
                {pinId
                  ? 'View and manage videos for this camera pin'
                  : mallId
                  ? 'View and manage videos for this mall'
                  : 'View and manage all videos across your malls'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {showUploader && mallId && pinId ? (
          /* Upload View */
          <div>
            <div className="mb-6">
              <button
                onClick={() => setShowUploader(false)}
                className="text-sm text-blue-600 hover:text-blue-700 flex items-center"
              >
                <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Back to Videos
              </button>
            </div>
            <VideoUploader
              mallId={mallId}
              pinId={pinId}
              onUploadComplete={handleUploadComplete}
              onUploadError={(error) => {
                console.error('Upload error:', error);
                alert('Upload failed: ' + error.message);
              }}
              onCancel={handleUploadCancel}
              maxSizeGB={2}
            />
          </div>
        ) : (
          /* List View */
          <VideoList
            mallId={mallId}
            pinId={pinId}
            showUploadButton={!!(mallId && pinId)}
            onUploadClick={handleUploadClick}
            onVideoClick={(videoId) => navigate(`/videos/${videoId}`)}
            enableDelete={true}
          />
        )}
      </div>
    </div>
  );
}

export default VideoListPage;
