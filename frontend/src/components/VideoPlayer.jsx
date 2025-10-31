/**
 * VideoPlayer Component
 *
 * HTML5 video player with custom controls for streaming CCTV footage.
 *
 * Features:
 * - Automatic signed URL loading and refresh
 * - Playback controls (play/pause, seek, volume, fullscreen)
 * - Playback speed control (0.5x, 1x, 1.5x, 2x)
 * - HTTP Range request support for seeking
 * - Video metadata display
 * - Error handling and loading states
 */

import React, { useState, useRef, useEffect } from 'react';
import { useSignedUrl, formatTimeRemaining } from '../hooks/useSignedUrl';

/**
 * VideoPlayer component for streaming videos with signed URLs.
 *
 * @param {Object} props - Component props
 * @param {string} props.videoId - Video UUID
 * @param {string} props.streamType - Stream type ('proxy' or 'original', default: 'proxy')
 * @param {Object} props.videoMetadata - Video metadata (optional)
 * @param {string} props.videoMetadata.filename - Original filename
 * @param {number} props.videoMetadata.duration_seconds - Video duration
 * @param {string} props.videoMetadata.uploaded_at - Upload timestamp
 * @param {string} props.videoMetadata.recorded_at - Recording timestamp
 * @param {string} props.videoMetadata.operator_notes - Operator notes
 * @param {boolean} props.autoPlay - Auto-play on load (default: false)
 * @param {boolean} props.showMetadata - Show metadata panel (default: true)
 * @param {Function} props.onError - Error callback
 */
export function VideoPlayer({
  videoId,
  streamType = 'proxy',
  videoMetadata = null,
  autoPlay = false,
  showMetadata = true,
  onError,
}) {
  // Video element ref
  const videoRef = useRef(null);

  // Playback state
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Fetch signed URL with auto-refresh
  const { url, loading, error, secondsUntilExpiry } = useSignedUrl(videoId, streamType, {
    expiresMinutes: 60,
    refreshBeforeMinutes: 5,
  });

  // Update video source when URL changes
  useEffect(() => {
    if (url && videoRef.current) {
      // Preserve current playback state before changing source
      const savedTime = videoRef.current.currentTime;
      const wasPlaying = !videoRef.current.paused;

      // Update source
      videoRef.current.src = url;

      // Restore playback state after metadata loads
      const handleLoadedMetadataForRestore = () => {
        if (videoRef.current) {
          // Restore time position
          videoRef.current.currentTime = savedTime;

          // Restore play state
          if (wasPlaying || autoPlay) {
            videoRef.current.play().catch(err => {
              console.error('Playback restoration failed:', err);
            });
          }
        }

        // Remove the one-time listener
        videoRef.current?.removeEventListener('loadedmetadata', handleLoadedMetadataForRestore);
      };

      // Listen for metadata load to restore state
      videoRef.current.addEventListener('loadedmetadata', handleLoadedMetadataForRestore);
    }
  }, [url, autoPlay]);

  // Video event handlers
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handlePlay = () => setPlaying(true);
  const handlePause = () => setPlaying(false);

  const handleError = (e) => {
    console.error('Video playback error:', e);
    if (onError) {
      onError(new Error('Video playback failed'));
    }
  };

  // Playback controls
  const togglePlayPause = () => {
    if (videoRef.current) {
      if (playing) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
    }
  };

  const handleSeek = (e) => {
    if (videoRef.current) {
      const seekTime = parseFloat(e.target.value);
      videoRef.current.currentTime = seekTime;
      setCurrentTime(seekTime);
    }
  };

  const handleVolumeChange = (e) => {
    if (videoRef.current) {
      const newVolume = parseFloat(e.target.value);
      videoRef.current.volume = newVolume;
      setVolume(newVolume);
      setMuted(newVolume === 0);
    }
  };

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !muted;
      setMuted(!muted);
    }
  };

  const changePlaybackRate = (rate) => {
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
      setPlaybackRate(rate);
    }
  };

  const toggleFullscreen = () => {
    if (!videoRef.current) return;

    if (!isFullscreen) {
      if (videoRef.current.requestFullscreen) {
        videoRef.current.requestFullscreen();
      } else if (videoRef.current.webkitRequestFullscreen) {
        videoRef.current.webkitRequestFullscreen();
      }
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      }
      setIsFullscreen(false);
    }
  };

  // Format time helper
  const formatTime = (seconds) => {
    if (isNaN(seconds) || seconds === 0) return '0:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-900 rounded-lg">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-white">Loading video...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-900 rounded-lg">
        <div className="text-center text-red-400">
          <svg className="mx-auto h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="font-medium">Video playback error</p>
          <p className="text-sm mt-2 text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Video Player */}
      <div className="relative bg-black rounded-lg overflow-hidden">
        <video
          ref={videoRef}
          className="w-full"
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={handleTimeUpdate}
          onPlay={handlePlay}
          onPause={handlePause}
          onError={handleError}
          controls={false}
        />

        {/* Custom Controls */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
          {/* Progress Bar */}
          <div className="mb-4">
            <input
              type="range"
              min="0"
              max={duration || 0}
              value={currentTime}
              onChange={handleSeek}
              className="w-full h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer slider"
            />
            <div className="flex justify-between text-xs text-white mt-1">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* Control Buttons */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {/* Play/Pause */}
              <button
                onClick={togglePlayPause}
                className="text-white hover:text-gray-300 transition"
              >
                {playing ? (
                  <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                ) : (
                  <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                  </svg>
                )}
              </button>

              {/* Volume */}
              <div className="flex items-center space-x-2">
                <button onClick={toggleMute} className="text-white hover:text-gray-300">
                  {muted || volume === 0 ? (
                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.707.707L4.586 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.586l3.707-3.707a1 1 0 011.09-.217zM12.293 7.293a1 1 0 011.414 0L15 8.586l1.293-1.293a1 1 0 111.414 1.414L16.414 10l1.293 1.293a1 1 0 01-1.414 1.414L15 11.414l-1.293 1.293a1 1 0 01-1.414-1.414L13.586 10l-1.293-1.293a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.707.707L4.586 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.586l3.707-3.707a1 1 0 011.09-.217zM14.657 2.929a1 1 0 011.414 0A9.972 9.972 0 0119 10a9.972 9.972 0 01-2.929 7.071 1 1 0 01-1.414-1.414A7.971 7.971 0 0017 10c0-2.21-.894-4.208-2.343-5.657a1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0A5.983 5.983 0 0115 10a5.984 5.984 0 01-1.757 4.243 1 1 0 01-1.415-1.415A3.984 3.984 0 0013 10a3.983 3.983 0 00-1.172-2.828 1 1 0 010-1.415z" clipRule="evenodd" />
                    </svg>
                  )}
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={muted ? 0 : volume}
                  onChange={handleVolumeChange}
                  className="w-20 h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer slider"
                />
              </div>

              {/* Playback Speed */}
              <select
                value={playbackRate}
                onChange={(e) => changePlaybackRate(parseFloat(e.target.value))}
                className="bg-gray-800 text-white text-sm px-2 py-1 rounded border border-gray-600"
              >
                <option value="0.5">0.5x</option>
                <option value="0.75">0.75x</option>
                <option value="1">1x</option>
                <option value="1.25">1.25x</option>
                <option value="1.5">1.5x</option>
                <option value="2">2x</option>
              </select>
            </div>

            {/* Fullscreen */}
            <button
              onClick={toggleFullscreen}
              className="text-white hover:text-gray-300 transition"
            >
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l2.293 2.293a1 1 0 11-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 010-2h4a1 1 0 011 1v4a1 1 0 01-2 0V6.414l-2.293 2.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 012 0v1.586l2.293-2.293a1 1 0 111.414 1.414L6.414 15H8a1 1 0 010 2H4a1 1 0 01-1-1v-4zm13-1a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 010-2h1.586l-2.293-2.293a1 1 0 111.414-1.414L15 13.586V12a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* URL Expiry Warning */}
      {secondsUntilExpiry !== null && secondsUntilExpiry < 300 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <p className="text-yellow-700 text-sm">
            ⚠️ Streaming URL expires in {formatTimeRemaining(secondsUntilExpiry)}. It will refresh automatically.
          </p>
        </div>
      )}

      {/* Video Metadata */}
      {showMetadata && videoMetadata && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Video Information</h3>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {videoMetadata.filename && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Filename</dt>
                <dd className="text-sm text-gray-900 mt-1">{videoMetadata.filename}</dd>
              </div>
            )}
            {videoMetadata.duration_seconds && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Duration</dt>
                <dd className="text-sm text-gray-900 mt-1">{formatTime(videoMetadata.duration_seconds)}</dd>
              </div>
            )}
            {videoMetadata.recorded_at && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Recorded At</dt>
                <dd className="text-sm text-gray-900 mt-1">
                  {new Date(videoMetadata.recorded_at).toLocaleString()}
                </dd>
              </div>
            )}
            {videoMetadata.uploaded_at && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Uploaded At</dt>
                <dd className="text-sm text-gray-900 mt-1">
                  {new Date(videoMetadata.uploaded_at).toLocaleString()}
                </dd>
              </div>
            )}
            {videoMetadata.operator_notes && (
              <div className="sm:col-span-2">
                <dt className="text-sm font-medium text-gray-500">Operator Notes</dt>
                <dd className="text-sm text-gray-900 mt-1">{videoMetadata.operator_notes}</dd>
              </div>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}

export default VideoPlayer;
