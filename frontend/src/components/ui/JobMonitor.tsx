'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { jobs } from '@/lib/api';
import type { Job } from '@/lib/types';

interface JobMonitorProps {
  jobId: number;
  onComplete: (job: Job) => void;
}

export default function JobMonitor({ jobId, onComplete }: JobMonitorProps) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const completedRef = useRef(false);

  const handleJobUpdate = useCallback(
    (updated: Job) => {
      setJob(updated);
      if (updated.status === 'completed' && !completedRef.current) {
        completedRef.current = true;
        onComplete(updated);
      }
      if (updated.status === 'failed') {
        setError(updated.error_message ?? 'Job failed with unknown error');
      }
    },
    [onComplete]
  );

  // Try WebSocket first, fall back to polling
  useEffect(() => {
    completedRef.current = false;
    setError(null);

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/jobs/${jobId}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as Job;
          handleJobUpdate(data);
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        // WebSocket failed, fall back to polling
        ws.close();
        startPolling();
      };

      ws.onclose = () => {
        // If not yet completed, start polling as fallback
        if (!completedRef.current) {
          startPolling();
        }
      };
    } catch {
      startPolling();
    }

    function startPolling() {
      if (intervalRef.current || completedRef.current) return;

      const poll = async () => {
        try {
          const data = await jobs.get(jobId);
          handleJobUpdate(data);
          if (data.status === 'completed' || data.status === 'failed') {
            if (intervalRef.current) clearInterval(intervalRef.current);
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Failed to fetch job status');
        }
      };

      poll();
      intervalRef.current = setInterval(poll, 2000);
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId, handleJobUpdate]);

  // Render
  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3">
        <svg
          className="h-5 w-5 flex-shrink-0 text-red-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div>
          <p className="text-sm font-medium text-red-800">Job Failed</p>
          <p className="text-xs text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  if (!job || job.status === 'queued' || job.status === 'pending' || job.status === 'running') {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
        {/* Spinner */}
        <svg
          className="h-5 w-5 animate-spin text-blue-600"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
          />
        </svg>
        <div className="flex-1">
          <p className="text-sm font-medium text-blue-800">
            {job?.status === 'running' ? 'Simulation running...' : 'Pending...'}
          </p>
          {/* Progress bar placeholder */}
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-blue-200">
            <div className="h-full animate-pulse rounded-full bg-blue-500" style={{ width: '60%' }} />
          </div>
        </div>
      </div>
    );
  }

  // Completed
  return (
    <div className="flex items-center gap-2 rounded-lg border border-green-300 bg-green-50 px-4 py-3">
      <svg
        className="h-5 w-5 text-green-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 13l4 4L19 7"
        />
      </svg>
      <p className="text-sm font-medium text-green-800">Job completed</p>
    </div>
  );
}
