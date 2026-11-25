import React, { useEffect, useState } from 'react';
import { 
  Activity, CheckCircle2, XCircle, Clock, AlertTriangle, 
  RotateCcw, X, Loader2, Film, Scissors, Volume2, Image as ImageIcon 
} from 'lucide-react';
import { api, JobData } from '../../services/api';

interface JobQueueProps {
  projectId?: string;
  className?: string;
  onJobCompleted?: (job: JobData) => void;
}

export const JobQueue: React.FC<JobQueueProps> = ({
  projectId,
  className = '',
  onJobCompleted,
}) => {
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = async () => {
    try {
      const data = await api.listJobs(projectId);
      setJobs(data);
    } catch (e) {
      console.warn('Failed to fetch jobs:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();

    // WebSocket connection for real-time updates
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket('ws://127.0.0.1:8000/ws/jobs');
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.event_type) {
            // Re-fetch or update in state
            fetchJobs();
          }
        } catch (err) {
          // Ignore parse errors
        }
      };
    } catch (e) {
      console.warn('WebSocket connection not available; using polling');
    }

    // Polling fallback every 3 seconds
    const interval = setInterval(fetchJobs, 3000);

    return () => {
      clearInterval(interval);
      if (ws) {
        ws.close();
      }
    };
  }, [projectId]);

  const handleCancel = async (jobId: string) => {
    try {
      await api.cancelJob(jobId);
      await fetchJobs();
    } catch (e) {
      console.error('Cancel job error:', e);
    }
  };

  const handleRetry = async (jobId: string) => {
    try {
      await api.retryJob(jobId);
      await fetchJobs();
    } catch (e) {
      console.error('Retry job error:', e);
    }
  };

  const getJobIcon = (type: string) => {
    switch (type) {
      case 'generate_clip':
        return <Scissors className="w-4 h-4 text-indigo-400" />;
      case 'extract_audio':
        return <Volume2 className="w-4 h-4 text-emerald-400" />;
      case 'generate_preview':
        return <Film className="w-4 h-4 text-amber-400" />;
      case 'thumbnail':
        return <ImageIcon className="w-4 h-4 text-purple-400" />;
      default:
        return <Activity className="w-4 h-4 text-zinc-400" />;
    }
  };

  const formatJobType = (type: string) => {
    switch (type) {
      case 'generate_clip':
        return 'Clip Rendering';
      case 'extract_audio':
        return 'Audio Extraction (16kHz)';
      case 'generate_preview':
        return 'Preview Generation (720p)';
      case 'thumbnail':
        return 'Thumbnail Generation';
      case 'inspect':
        return 'Video Inspection';
      default:
        return type.replace('_', ' ');
    }
  };

  return (
    <div className={`bg-zinc-900 border border-zinc-800 rounded-xl p-4 shadow-lg ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-white">Video Processing Queue</h3>
        </div>
        <span className="text-xs font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded-full">
          {jobs.filter((j) => j.status === 'running' || j.status === 'queued').length} active
        </span>
      </div>

      {loading && jobs.length === 0 ? (
        <div className="flex items-center justify-center p-6 text-zinc-500 text-xs">
          <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading jobs...
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-6 text-zinc-500 text-xs">
          No video tasks currently running or queued.
        </div>
      ) : (
        <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
          {jobs.slice(0, 10).map((job) => {
            const isRunning = job.status === 'running';
            const isQueued = job.status === 'queued';
            const isCompleted = job.status === 'completed';
            const isFailed = job.status === 'failed';
            const isCancelled = job.status === 'cancelled';

            return (
              <div
                key={job.id}
                className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-lg hover:border-zinc-700 transition-colors"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    {getJobIcon(job.job_type)}
                    <span className="text-xs font-medium text-zinc-200">
                      {formatJobType(job.job_type)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {isRunning && (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-indigo-400">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        {job.progress_percent}%
                      </span>
                    )}

                    {isQueued && (
                      <span className="flex items-center gap-1 text-[11px] text-zinc-400">
                        <Clock className="w-3 h-3" /> Queued
                      </span>
                    )}

                    {isCompleted && (
                      <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                        <CheckCircle2 className="w-3 h-3" /> Done
                      </span>
                    )}

                    {isFailed && (
                      <span className="flex items-center gap-1 text-[11px] text-rose-400 font-medium">
                        <AlertTriangle className="w-3 h-3" /> Failed
                      </span>
                    )}

                    {isCancelled && (
                      <span className="flex items-center gap-1 text-[11px] text-zinc-500">
                        <XCircle className="w-3 h-3" /> Cancelled
                      </span>
                    )}

                    {/* Actions */}
                    {(isRunning || isQueued) && (
                      <button
                        onClick={() => handleCancel(job.id)}
                        className="p-1 text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 rounded transition-colors ml-1"
                        title="Cancel task"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}

                    {(isFailed || isCancelled) && (
                      <button
                        onClick={() => handleRetry(job.id)}
                        className="p-1 text-zinc-400 hover:text-indigo-400 hover:bg-zinc-800 rounded transition-colors ml-1"
                        title="Retry task"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar */}
                {(isRunning || isQueued) && (
                  <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden my-1.5">
                    <div
                      className={`h-full transition-all duration-300 ${
                        isRunning ? 'bg-indigo-500' : 'bg-zinc-600 animate-pulse'
                      }`}
                      style={{ width: `${job.progress_percent}%` }}
                    />
                  </div>
                )}

                {/* Stage description or error */}
                <div className="text-[11px] text-zinc-400 truncate">
                  {job.error_message ? (
                    <span className="text-rose-400 font-mono text-[10px]">
                      {job.error_message}
                    </span>
                  ) : (
                    <span>{job.stage_description || 'In progress...'}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
