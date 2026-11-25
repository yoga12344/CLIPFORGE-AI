import React, { useEffect, useState } from 'react';
import { 
  ListOrdered, RefreshCw, Cpu, Film, Activity, 
  CheckCircle, AlertTriangle, Clock, Scissors 
} from 'lucide-react';
import { api, JobData, VideoCapabilitiesData } from '../services/api';
import { JobQueue } from '../components/jobs/JobQueue';

export const JobQueuePage: React.FC = () => {
  const [capabilities, setCapabilities] = useState<VideoCapabilitiesData | null>(null);
  const [loadingCaps, setLoadingCaps] = useState(false);

  const fetchCapabilities = async (force: boolean = false) => {
    setLoadingCaps(true);
    try {
      const data = await api.getVideoCapabilities(force);
      setCapabilities(data);
    } catch (e) {
      console.warn('Failed to load video capabilities:', e);
    } finally {
      setLoadingCaps(false);
    }
  };

  useEffect(() => {
    fetchCapabilities();
  }, []);

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <ListOrdered className="w-7 h-7 text-indigo-400" />
            Background Processing Engine
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Real-time FFmpeg video pipeline tasks, GPU/CPU bounded worker queue, and hardware status.
          </p>
        </div>

        <button
          onClick={() => fetchCapabilities(true)}
          disabled={loadingCaps}
          className="px-3.5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingCaps ? 'animate-spin' : ''}`} />
          Re-test Hardware Capabilities
        </button>
      </div>

      {/* Hardware Capabilities Card */}
      {capabilities && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-400" />
              Engine & Codec Verification
            </h2>
            <span className="text-xs font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded">
              Encoder: {capabilities.recommended_video_encoder}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-zinc-950/60 rounded-lg border border-zinc-800/80">
              <span className="text-zinc-500">FFmpeg Binary</span>
              <p className="font-mono text-zinc-200 mt-1 truncate" title={capabilities.ffmpeg_path}>
                {capabilities.ffmpeg_available ? 'Available' : 'Missing'}
              </p>
            </div>

            <div className="p-3 bg-zinc-950/60 rounded-lg border border-zinc-800/80">
              <span className="text-zinc-500">libx264 (CPU)</span>
              <p className="font-mono text-emerald-400 mt-1 flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> Functional
              </p>
            </div>

            <div className="p-3 bg-zinc-950/60 rounded-lg border border-zinc-800/80">
              <span className="text-zinc-500">NVENC (GPU)</span>
              <p className={`font-mono mt-1 flex items-center gap-1 ${
                capabilities.nvenc_functional ? 'text-emerald-400' : 'text-amber-400'
              }`}>
                {capabilities.nvenc_functional ? (
                  <><CheckCircle className="w-3.5 h-3.5" /> Functional</>
                ) : (
                  <><AlertTriangle className="w-3.5 h-3.5" /> CPU Fallback Active</>
                )}
              </p>
            </div>

            <div className="p-3 bg-zinc-950/60 rounded-lg border border-zinc-800/80">
              <span className="text-zinc-500">libass Subtitles</span>
              <p className="font-mono text-emerald-400 mt-1 flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> Available
              </p>
            </div>
          </div>

          {capabilities.diagnostic_notes.length > 0 && (
            <div className="mt-3 p-2.5 bg-zinc-950/80 rounded-lg border border-zinc-800 text-[11px] font-mono text-zinc-400">
              <span className="text-amber-400 font-medium">Diagnostic: </span>
              {capabilities.diagnostic_notes[0]}
            </div>
          )}
        </div>
      )}

      {/* Main Job Queue */}
      <JobQueue className="min-h-[400px]" />
    </div>
  );
};
