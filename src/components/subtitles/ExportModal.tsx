import React, { useState } from 'react';
import {
  Film,
  Download,
  Play,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  Ratio,
  Sliders,
  Type,
  X,
} from 'lucide-react';
import { Modal } from '../ui/Modal';
import { api, CaptionPresetData, ExportData } from '../../services/api';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  clipId: string;
  clipTitle: string;
  activePreset?: CaptionPresetData;
  onExportSuccess?: (exportRecord: ExportData) => void;
}

const RESOLUTIONS = [
  { id: '1080x1920', label: '9:16 Vertical', desc: 'TikTok, Reels, YouTube Shorts', icon: '📱' },
  { id: '1080x1080', label: '1:1 Square', desc: 'Instagram, Twitter / X', icon: '⏹' },
  { id: '1080x1350', label: '4:5 Portrait', desc: 'Facebook Feed & LinkedIn', icon: '🖼' },
  { id: '1920x1080', label: '16:9 Landscape', desc: 'Standard YouTube Video', icon: '🖥' },
];

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  clipId,
  clipTitle,
  activePreset,
  onExportSuccess,
}) => {
  const [resolution, setResolution] = useState('1080x1920');
  const [bitrate, setBitrate] = useState(6000);
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [useVisionTracking, setUseVisionTracking] = useState(true);

  // Job progress state
  const [isRendering, setIsRendering] = useState(false);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStage, setJobStage] = useState('');
  const [completedExport, setCompletedExport] = useState<ExportData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleStartRender = async () => {
    setIsRendering(true);
    setError(null);
    setJobProgress(0);
    setJobStage('Initializing export job...');
    setCompletedExport(null);

    try {
      const res = await api.renderClipExport(clipId, {
        preset_id: activePreset?.id,
        resolution,
        bitrate_kbps: bitrate,
        burn_subtitles: burnSubtitles,
        use_vision_tracking: useVisionTracking,
        reframe_mode: useVisionTracking ? 'smart_face_track' : 'center_crop',
      });

      // Poll job progress
      const pollTimer = setInterval(async () => {
        try {
          const job = await api.getJob(res.job_id);
          setJobProgress(job.progress_percent);
          setJobStage(job.stage_description || 'Rendering frames...');

          if (job.status === 'completed') {
            clearInterval(pollTimer);
            setIsRendering(false);
            // Fetch export details
            const exports = await api.getClipExports(clipId);
            if (exports.length > 0) {
              setCompletedExport(exports[0]);
              if (onExportSuccess) onExportSuccess(exports[0]);
            }
          } else if (job.status === 'failed' || job.status === 'cancelled') {
            clearInterval(pollTimer);
            setIsRendering(false);
            setError(job.error_message || 'Video render failed');
          }
        } catch (pollErr) {
          console.warn('Poll error:', pollErr);
        }
      }, 1200);
    } catch (e: any) {
      setIsRendering(false);
      setError(e.message || 'Failed to start export');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Export Final Clip">
      <div className="space-y-4 text-xs">
        {/* Clip Title Banner */}
        <div className="p-3 rounded-lg border border-border-muted bg-surface-muted/40 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-text-muted">Target Clip</div>
            <div className="font-semibold text-text-primary text-xs mt-0.5 truncate max-w-sm">
              {clipTitle}
            </div>
          </div>
          {activePreset && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30">
              Style: {activePreset.name}
            </span>
          )}
        </div>

        {/* 1. Resolution & Aspect Ratio Selection */}
        <div>
          <label className="block text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2">
            Target Platform & Aspect Ratio
          </label>
          <div className="grid grid-cols-2 gap-2">
            {RESOLUTIONS.map((r) => {
              const isSelected = resolution === r.id;
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setResolution(r.id)}
                  className={`p-2.5 rounded-lg border text-left transition-all ${
                    isSelected
                      ? 'border-primary bg-primary/10 text-text-primary'
                      : 'border-border-muted bg-surface-muted/30 text-text-muted hover:border-border-base'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-semibold text-xs mb-0.5">
                    <span>{r.icon}</span>
                    <span>{r.label}</span>
                  </div>
                  <div className="text-[10px] text-text-muted">{r.desc}</div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. Options: Subtitle Burn & Vision Tracking */}
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border-base">
          <label className="flex items-start gap-2 p-2.5 rounded-lg border border-border-muted bg-surface-muted/20 cursor-pointer">
            <input
              type="checkbox"
              checked={burnSubtitles}
              onChange={(e) => setBurnSubtitles(e.target.checked)}
              className="mt-0.5 accent-primary"
            />
            <div>
              <div className="font-semibold text-xs text-text-primary">Burn Subtitles</div>
              <div className="text-[10px] text-text-muted">Karaoke styled captions</div>
            </div>
          </label>

          <label className="flex items-start gap-2 p-2.5 rounded-lg border border-border-muted bg-surface-muted/20 cursor-pointer">
            <input
              type="checkbox"
              checked={useVisionTracking}
              onChange={(e) => setUseVisionTracking(e.target.checked)}
              className="mt-0.5 accent-primary"
            />
            <div>
              <div className="font-semibold text-xs text-text-primary">Smart Reframing</div>
              <div className="text-[10px] text-text-muted">Dynamic face tracking</div>
            </div>
          </label>
        </div>

        {/* 3. Bitrate Slider */}
        <div className="pt-2 border-t border-border-base">
          <div className="flex justify-between text-[11px] text-text-muted mb-1">
            <span>Video Bitrate</span>
            <span className="font-mono text-text-primary font-bold">{bitrate} kbps</span>
          </div>
          <input
            type="range"
            min="3000"
            max="12000"
            step="500"
            value={bitrate}
            onChange={(e) => setBitrate(parseInt(e.target.value))}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[9px] text-text-muted mt-0.5">
            <span>Compact (Fast)</span>
            <span>Master Quality (Sharp)</span>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-xs">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Progress Display */}
        {isRendering && (
          <div className="p-3 rounded-lg border border-primary/20 bg-primary/5 space-y-2">
            <div className="flex items-center justify-between font-medium">
              <span className="flex items-center gap-1.5 text-text-primary text-xs">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                <span>Rendering Final MP4 Video...</span>
              </span>
              <span className="font-mono text-primary font-bold">{jobProgress}%</span>
            </div>
            <div className="w-full h-1.5 bg-surface-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${jobProgress}%` }}
              />
            </div>
            <div className="text-[10px] text-text-muted italic">{jobStage}</div>
          </div>
        )}

        {/* Completed Card */}
        {completedExport && (
          <div className="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 space-y-3">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs">
              <CheckCircle2 className="w-4 h-4" />
              <span>Video Exported Successfully!</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-[10px] text-text-muted border-t border-emerald-500/20 pt-2">
              <div>
                <span>Resolution</span>
                <div className="font-bold text-text-primary text-xs">{completedExport.resolution}</div>
              </div>
              <div>
                <span>Duration</span>
                <div className="font-bold text-text-primary text-xs">{completedExport.duration_seconds}s</div>
              </div>
              <div>
                <span>File Size</span>
                <div className="font-bold text-text-primary text-xs">
                  {Math.round((completedExport.file_size_bytes || 0) / 1024)} KB
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <a
                href={api.getExportDownloadUrl(completedExport.id)}
                download
                className="flex-1 py-2 px-3 bg-primary hover:bg-primary/90 text-black font-semibold rounded-lg text-xs flex items-center justify-center gap-1.5 shadow"
              >
                <Download className="w-3.5 h-3.5" /> Download MP4
              </a>
            </div>
          </div>
        )}

        {/* Footer Actions */}
        {!completedExport && (
          <div className="flex justify-end gap-2 pt-3 border-t border-border-base">
            <button
              type="button"
              onClick={onClose}
              disabled={isRendering}
              className="py-2 px-4 rounded-lg border border-border-muted text-text-muted hover:text-white text-xs"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleStartRender}
              disabled={isRendering}
              className="py-2 px-5 bg-primary hover:bg-primary/90 text-black font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-md disabled:opacity-50"
            >
              {isRendering ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Rendering...</span>
                </>
              ) : (
                <>
                  <Film className="w-3.5 h-3.5" />
                  <span>Render Video</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
};
