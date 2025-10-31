/**
 * Custom React hook for polling processing job status.
 *
 * Automatically polls the job status API every 3 seconds until the job
 * is completed or failed. Provides loading and error states.
 *
 * @example
 * function VideoUploadProgress({ jobId }) {
 *   const { status, loading, error } = useJobStatus(jobId);
 *
 *   if (loading) return <div>Loading...</div>;
 *   if (error) return <div>Error: {error}</div>;
 *
 *   return (
 *     <div>
 *       {status === 'pending' && 'Processing queued...'}
 *       {status === 'running' && 'Processing video...'}
 *       {status === 'completed' && '✅ Processing complete!'}
 *       {status === 'failed' && '❌ Processing failed'}
 *     </div>
 *   );
 * }
 */

import { useState, useEffect, useRef } from 'react';
import { getJobStatus } from '../services/videoService';

/**
 * Hook for polling job status.
 *
 * @param {string} jobId - Processing job UUID
 * @param {Object} options - Hook options
 * @param {number} options.pollInterval - Polling interval in milliseconds (default: 3000)
 * @param {boolean} options.enabled - Whether polling is enabled (default: true)
 * @returns {Object} - Job status state
 * @returns {Object} returns.job - Full job object from API
 * @returns {string} returns.status - Job status ('pending', 'running', 'completed', 'failed', null)
 * @returns {boolean} returns.loading - Whether initial load is in progress
 * @returns {string} returns.error - Error message if request failed
 * @returns {boolean} returns.isPolling - Whether currently polling
 */
export function useJobStatus(jobId, options = {}) {
  const {
    pollInterval = 3000,
    enabled = true,
  } = options;

  const [job, setJob] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isPolling, setIsPolling] = useState(false);

  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    // Skip if no job ID or polling disabled
    if (!jobId || !enabled) {
      setLoading(false);
      return;
    }

    // Fetch job status
    const fetchStatus = async () => {
      try {
        const jobData = await getJobStatus(jobId);

        // Only update state if component is still mounted
        if (!mountedRef.current) return;

        setJob(jobData);
        setStatus(jobData.status);
        setError(null);
        setLoading(false);

        // Stop polling if job is completed or failed
        if (jobData.status === 'completed' || jobData.status === 'failed') {
          setIsPolling(false);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch (err) {
        if (!mountedRef.current) return;

        console.error('Failed to fetch job status:', err);
        setError(err.message || 'Failed to fetch job status');
        setLoading(false);
        setIsPolling(false);

        // Stop polling on error
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    };

    // Initial fetch
    fetchStatus();
    setIsPolling(true);

    // Start polling
    intervalRef.current = setInterval(fetchStatus, pollInterval);

    // Cleanup on unmount or when jobId/enabled changes
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsPolling(false);
    };
  }, [jobId, enabled, pollInterval]);

  return {
    job,
    status,
    loading,
    error,
    isPolling,
  };
}

/**
 * Hook for polling multiple job statuses.
 *
 * Useful when tracking multiple uploads/processing jobs simultaneously.
 *
 * @param {string[]} jobIds - Array of job UUIDs
 * @param {Object} options - Hook options
 * @param {number} options.pollInterval - Polling interval in milliseconds (default: 3000)
 * @returns {Object} - Job statuses map
 * @returns {Object} returns.jobs - Map of jobId → job object
 * @returns {Object} returns.statuses - Map of jobId → status string
 * @returns {boolean} returns.loading - Whether any job is loading
 * @returns {Object} returns.errors - Map of jobId → error message
 * @returns {boolean} returns.allComplete - Whether all jobs are completed or failed
 *
 * @example
 * const { statuses, allComplete } = useMultipleJobStatuses([jobId1, jobId2, jobId3]);
 *
 * if (allComplete) {
 *   console.log('All processing jobs complete!');
 * }
 */
export function useMultipleJobStatuses(jobIds, options = {}) {
  const { pollInterval = 3000 } = options;

  const [jobs, setJobs] = useState({});
  const [statuses, setStatuses] = useState({});
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});

  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!jobIds || jobIds.length === 0) {
      setLoading(false);
      return;
    }

    const fetchStatuses = async () => {
      const newJobs = {};
      const newStatuses = {};
      const newErrors = {};

      await Promise.all(
        jobIds.map(async (jobId) => {
          try {
            const jobData = await getJobStatus(jobId);
            newJobs[jobId] = jobData;
            newStatuses[jobId] = jobData.status;
          } catch (err) {
            console.error(`Failed to fetch status for job ${jobId}:`, err);
            newErrors[jobId] = err.message;
          }
        })
      );

      if (!mountedRef.current) return;

      setJobs(newJobs);
      setStatuses(newStatuses);
      setErrors(newErrors);
      setLoading(false);

      // Check if all jobs are complete
      const allComplete = jobIds.every(
        (jobId) =>
          newStatuses[jobId] === 'completed' || newStatuses[jobId] === 'failed'
      );

      // Stop polling if all complete
      if (allComplete && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    // Initial fetch
    fetchStatuses();

    // Start polling
    intervalRef.current = setInterval(fetchStatuses, pollInterval);

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobIds, pollInterval]);

  const allComplete = jobIds.every(
    (jobId) => statuses[jobId] === 'completed' || statuses[jobId] === 'failed'
  );

  return {
    jobs,
    statuses,
    loading,
    errors,
    allComplete,
  };
}

export default useJobStatus;
