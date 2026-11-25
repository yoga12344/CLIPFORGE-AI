import React, { useState, useEffect } from 'react';
import { 
  Sparkles, RefreshCw, Loader2, AlertCircle, 
  Layers, Check, Scissors 
} from 'lucide-react';
import { api, HighlightCandidateData } from '../../services/api';
import { HighlightCandidateList } from './HighlightCandidateList';
import { HighlightSettingsModal } from './HighlightSettingsModal';
import { Modal } from '../ui/Modal';

interface HighlightAnalysisPanelProps {
  videoId: string;
  projectId: string;
  currentTime: number;
  onSeek: (time: number) => void;
  className?: string;
  onClipCreated?: () => void;
}

export const HighlightAnalysisPanel: React.FC<HighlightAnalysisPanelProps> = ({
  videoId,
  projectId,
  currentTime,
  onSeek,
  className = '',
  onClipCreated,
}) => {
  const [candidates, setCandidates] = useState<HighlightCandidateData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeClipModalCandidate, setActiveClipModalCandidate] = useState<HighlightCandidateData | null>(null);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [reframeMode, setReframeMode] = useState('center_crop');
  const [isSubmittingClip, setIsSubmittingClip] = useState(false);

  const loadCandidates = async () => {
    setIsLoading(true);
    try {
      const data = await api.listHighlightCandidates(videoId);
      setCandidates(data);
    } catch (e) {
      console.warn('Failed to load highlight candidates:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (videoId) {
      loadCandidates();
    }
  }, [videoId]);

  const handleStartAnalysis = async (params: {
    model_name: string;
    content_type: string;
    target_duration_min: number;
    target_duration_max: number;
    max_candidates: number;
    auto_create_clips?: boolean;
  }) => {
    setIsLoading(true);
    try {
      const res = await api.analyzeHighlights(videoId, params);
      const pollTimer = setInterval(async () => {
        try {
          const job = await api.getJob(res.job_id);
          if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
            clearInterval(pollTimer);
            await loadCandidates();
            if (onClipCreated) {
              onClipCreated();
            }
          }
        } catch {
          // ignore transient poll error
        }
      }, 1500);
    } catch (err) {
      console.error('Failed to trigger highlight analysis:', err);
      setIsLoading(false);
    }
  };

  const handleApprove = async (candidateId: string) => {
    try {
      const updated = await api.approveHighlightCandidate(candidateId);
      setCandidates((prev) => prev.map((c) => (c.id === candidateId ? updated : c)));
    } catch (e) {
      console.error('Failed to approve candidate:', e);
    }
  };

  const handleReject = async (candidateId: string) => {
    try {
      const updated = await api.rejectHighlightCandidate(candidateId);
      setCandidates((prev) => prev.map((c) => (c.id === candidateId ? updated : c)));
    } catch (e) {
      console.error('Failed to reject candidate:', e);
    }
  };

  const handleEdit = async (candidateId: string, startTime: number, endTime: number, title: string) => {
    try {
      const updated = await api.updateHighlightCandidate(candidateId, {
        start_time: startTime,
        end_time: endTime,
        title,
      });
      setCandidates((prev) => prev.map((c) => (c.id === candidateId ? updated : c)));
    } catch (e) {
      console.error('Failed to update candidate:', e);
    }
  };

  const handleConfirmCreateClip = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeClipModalCandidate) return;
    setIsSubmittingClip(true);
    try {
      await api.createClipFromHighlight(activeClipModalCandidate.id, {
        aspect_ratio: aspectRatio,
        reframe_mode: reframeMode,
      });
      setActiveClipModalCandidate(null);
      await loadCandidates();
      if (onClipCreated) {
        onClipCreated();
      }
    } catch (err) {
      console.error('Failed to render clip from candidate:', err);
    } finally {
      setIsSubmittingClip(false);
    }
  };

  return (
    <div className={`bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col h-full overflow-hidden ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-zinc-800 flex items-center justify-between flex-shrink-0 bg-zinc-900/90">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-white">
            AI Highlight Discovery
          </h3>
          <span className="text-xs text-zinc-500 font-mono">
            ({candidates.length})
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadCandidates}
            className="p-1.5 hover:bg-zinc-800 text-zinc-400 hover:text-white rounded-lg transition-colors"
            title="Refresh candidate highlights"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setIsSettingsOpen(true)}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-md shadow-indigo-600/20 transition-all flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5 fill-current" />
            Discover Highlights
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4">
        <HighlightCandidateList
          candidates={candidates}
          isLoading={isLoading}
          onPreview={(startTime) => onSeek(startTime)}
          onApprove={handleApprove}
          onReject={handleReject}
          onEdit={handleEdit}
          onCreateClip={(candidate) => setActiveClipModalCandidate(candidate)}
          onOpenDiscoveryModal={() => setIsSettingsOpen(true)}
        />
      </div>

      {/* Discovery Settings Modal */}
      <HighlightSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onStartAnalysis={handleStartAnalysis}
      />

      {/* Render Clip Confirmation Modal */}
      {activeClipModalCandidate && (
        <Modal
          isOpen={!!activeClipModalCandidate}
          onClose={() => setActiveClipModalCandidate(null)}
          title={`Render Clip: ${activeClipModalCandidate.title}`}
        >
          <form onSubmit={handleConfirmCreateClip} className="space-y-4 text-xs">
            <div className="p-3 bg-zinc-950/80 rounded-lg border border-zinc-800 space-y-1">
              <div className="flex justify-between font-mono text-[11px] text-zinc-400">
                <span>Timestamps:</span>
                <span className="text-zinc-200">
                  {activeClipModalCandidate.start_time.toFixed(1)}s - {activeClipModalCandidate.end_time.toFixed(1)}s
                </span>
              </div>
              <div className="flex justify-between font-mono text-[11px] text-zinc-400">
                <span>Duration:</span>
                <span className="text-indigo-400 font-semibold">
                  {activeClipModalCandidate.duration_seconds.toFixed(1)}s
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-zinc-300 font-medium mb-1">Aspect Ratio</label>
                <select
                  value={aspectRatio}
                  onChange={(e) => setAspectRatio(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="9:16">9:16 (TikTok, Shorts, Reels)</option>
                  <option value="1:1">1:1 (Instagram Feed)</option>
                  <option value="4:5">4:5 (Portrait Feed)</option>
                  <option value="16:9">16:9 (Landscape)</option>
                </select>
              </div>

              <div>
                <label className="block text-zinc-300 font-medium mb-1">Reframing Mode</label>
                <select
                  value={reframeMode}
                  onChange={(e) => setReframeMode(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="center_crop">Center Crop (Full Fill)</option>
                  <option value="blur_background">Blurred Background</option>
                  <option value="fit_pad">Fit with Black Bars</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setActiveClipModalCandidate(null)}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmittingClip}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                {isSubmittingClip ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Scissors className="w-3.5 h-3.5" />
                )}
                Render Clip Now
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
