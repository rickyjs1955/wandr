/**
 * Custom React hook for managing signed streaming URLs.
 *
 * Automatically fetches signed URLs and refreshes them before expiry
 * to ensure uninterrupted video playback.
 *
 * @example
 * function VideoPlayer({ videoId }) {
 *   const { url, loading, error } = useSignedUrl(videoId, 'proxy');
 *
 *   if (loading) return <div>Loading...</div>;
 *   if (error) return <div>Error: {error}</div>;
 *
 *   return <video src={url} controls />;
 * }
 */

import { useState, useEffect, useRef } from 'react';
import { getStreamUrl, getThumbnailUrl } from '../services/videoService';

/**
 * Hook for managing signed streaming URLs with automatic refresh.
 *
 * @param {string} videoId - Video UUID
 * @param {string} streamType - Stream type ('proxy' or 'original')
 * @param {Object} options - Hook options
 * @param {number} options.expiresMinutes - URL expiration time (default: 60)
 * @param {number} options.refreshBeforeMinutes - Refresh URL N minutes before expiry (default: 5)
 * @param {boolean} options.enabled - Whether fetching is enabled (default: true)
 * @returns {Object} - Signed URL state
 * @returns {string} returns.url - Presigned streaming URL
 * @returns {string} returns.expiresAt - ISO 8601 datetime when URL expires
 * @returns {boolean} returns.loading - Whether initial load is in progress
 * @returns {string} returns.error - Error message if request failed
 * @returns {number} returns.secondsUntilExpiry - Seconds until URL expires
 */
export function useSignedUrl(videoId, streamType = 'proxy', options = {}) {
  const {
    expiresMinutes = 60,
    refreshBeforeMinutes = 5,
    enabled = true,
  } = options;

  const [url, setUrl] = useState(null);
  const [expiresAt, setExpiresAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [secondsUntilExpiry, setSecondsUntilExpiry] = useState(null);

  const refreshTimeoutRef = useRef(null);
  const countdownIntervalRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // Skip if no video ID or disabled
    if (!videoId || !enabled) {
      setLoading(false);
      return;
    }

    // Fetch signed URL
    const fetchSignedUrl = async () => {
      try {
        const response = await getStreamUrl(videoId, streamType, expiresMinutes);

        // Only update state if component is still mounted
        if (!mountedRef.current) return;

        setUrl(response.url);
        setExpiresAt(response.expires_at);
        setError(null);
        setLoading(false);

        // Calculate seconds until expiry
        const expiryTime = new Date(response.expires_at).getTime();
        const now = Date.now();
        const seconds = Math.floor((expiryTime - now) / 1000);
        setSecondsUntilExpiry(seconds);

        // Schedule refresh before expiry
        const refreshTime = (expiresMinutes - refreshBeforeMinutes) * 60 * 1000;
        if (refreshTime > 0) {
          refreshTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
              fetchSignedUrl(); // Refresh URL
            }
          }, refreshTime);
        }

        // Clear any existing countdown interval before starting a new one
        if (countdownIntervalRef.current) {
          clearInterval(countdownIntervalRef.current);
          countdownIntervalRef.current = null;
        }

        // Start countdown timer (update every 10 seconds)
        countdownIntervalRef.current = setInterval(() => {
          if (!mountedRef.current) return;

          const expiryTime = new Date(response.expires_at).getTime();
          const now = Date.now();
          const seconds = Math.floor((expiryTime - now) / 1000);
          setSecondsUntilExpiry(seconds > 0 ? seconds : 0);
        }, 10000); // Update every 10 seconds

      } catch (err) {
        if (!mountedRef.current) return;

        console.error('Failed to fetch signed URL:', err);
        setError(err.message || 'Failed to fetch streaming URL');
        setLoading(false);
      }
    };

    // Initial fetch
    fetchSignedUrl();

    // Cleanup on unmount or when dependencies change
    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current);
        refreshTimeoutRef.current = null;
      }
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
      }
    };
  }, [videoId, streamType, enabled, expiresMinutes, refreshBeforeMinutes]);

  return {
    url,
    expiresAt,
    loading,
    error,
    secondsUntilExpiry,
  };
}

/**
 * Hook for managing thumbnail URLs.
 *
 * @param {string} videoId - Video UUID
 * @param {Object} options - Hook options
 * @param {number} options.expiresMinutes - URL expiration time (default: 60)
 * @param {boolean} options.enabled - Whether fetching is enabled (default: true)
 * @returns {Object} - Thumbnail URL state
 * @returns {string} returns.url - Presigned thumbnail URL
 * @returns {boolean} returns.loading - Whether initial load is in progress
 * @returns {string} returns.error - Error message if request failed
 */
export function useThumbnailUrl(videoId, options = {}) {
  const {
    expiresMinutes = 60,
    enabled = true,
  } = options;

  const [url, setUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // Skip if no video ID or disabled
    if (!videoId || !enabled) {
      setLoading(false);
      return;
    }

    // Fetch thumbnail URL
    const fetchThumbnailUrl = async () => {
      try {
        const response = await getThumbnailUrl(videoId, expiresMinutes);

        if (!mountedRef.current) return;

        setUrl(response.url);
        setError(null);
        setLoading(false);
      } catch (err) {
        if (!mountedRef.current) return;

        console.error('Failed to fetch thumbnail URL:', err);
        setError(err.message || 'Failed to fetch thumbnail');
        setLoading(false);
      }
    };

    fetchThumbnailUrl();
  }, [videoId, enabled, expiresMinutes]);

  return {
    url,
    loading,
    error,
  };
}

/**
 * Format seconds to human-readable time string.
 *
 * @param {number} seconds - Seconds to format
 * @returns {string} - Formatted time (e.g., "5 minutes", "2 hours 30 minutes")
 *
 * @example
 * formatTimeRemaining(300) // "5 minutes"
 * formatTimeRemaining(9000) // "2 hours 30 minutes"
 */
export function formatTimeRemaining(seconds) {
  if (seconds <= 0) return 'Expired';
  if (seconds < 60) return `${seconds} seconds`;
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    return `${minutes} minute${minutes > 1 ? 's' : ''}`;
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (minutes === 0) {
    return `${hours} hour${hours > 1 ? 's' : ''}`;
  }

  return `${hours} hour${hours > 1 ? 's' : ''} ${minutes} minute${minutes > 1 ? 's' : ''}`;
}

export default useSignedUrl;
