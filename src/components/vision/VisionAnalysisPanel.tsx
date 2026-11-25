import React, { useEffect, useState } from 'react';
import {
  Eye,
  Sliders,
  Play,
  RotateCcw,
  Sparkles,
  Users,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Film,
  Camera,
  Layers,
} from 'lucide-react';
import {
  api,
  VisionAnalysisData,
  TrackedFaceData,
  CropCoordinateData,
  ReframeConfigData,
} from '../../services/api';
import { ReframeSettingsPanel } from './ReframeSettingsPanel';
import { CropPreview } from './CropPreview';

interface VisionAnalysisPanelProps {
  videoId?: string;
  projectId?: string;
  currentTime: number;
  videoDuration: number;
  videoSrc?: string;
  onSeek?: (seconds: number) => void;
  onCropChange?: (crop: CropCoordinateData | null) => void;
  onTracksChange?: (tracks: TrackedFaceData[]) => void;
}

export const VisionAnalysisPanel: React.FC<VisionAnalysisPanelProps> = ({
  videoId,
  projectId,
  currentTime,
  videoDuration,
  videoSrc = '',
  onSeek,
  onCropChange,
  onTracksChange,
}) => {
  const [analysis, setAnalysis] = useState<VisionAnalysisData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<number>(0);
  const [jobStage, setJobStage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  // Reframe Configuration
  const [reframeConfig, setReframeConfig] = useState<ReframeConfigData>({
    aspect_ratio: '9:16',
    strategy: 'largest_face',
    selected_track_id: undefined,
    smoothing_strength: 0.85,
    crop_padding: 0.15,
    headroom: 0.20,
    max_crop_velocity_per_sec: 0.50,
    face_confidence_threshold: 0.55,
    sampling_fps: 4.0,
  });

  // Trajectory coordinates
  const [trajectory, setTrajectory] = useState<CropCoordinateData[]>([]);
  const [isComputingTrajectory, setIsComputingTrajectory] = useState(false);

  // Load existing analysis on videoId change
  const loadAnalysis = async () => {
    if (!videoId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getVideoVisualAnalysis(videoId);
      setAnalysis(data);
      if (data && data.tracks) {
        if (onTracksChange) onTracksChange(data.tracks);
        // Compute trajectory automatically if analysis exists
        await computeTrajectory(data.id, reframeConfig);
      }
    } catch (e: any) {
      console.warn('Failed to load visual analysis:', e);
      setError(e.message || 'Failed to fetch visual analysis');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAnalysis();
  }, [videoId]);

  // Compute trajectory whenever reframe config changes and analysis exists
  const computeTrajectory = async (analysisId: string, cfg: ReframeConfigData) => {
    setIsComputingTrajectory(true);
    try {
      const coords = await api.calculateReframeTrajectory(analysisId, cfg);
      setTrajectory(coords);
    } catch (e: any) {
      console.warn('Failed to compute trajectory:', e);
    } finally {
      setIsComputingTrajectory(false);
    }
  };

  const handleConfigChange = async (newConfig: ReframeConfigData) => {
    setReframeConfig(newConfig);
    if (analysis) {
      await computeTrajectory(analysis.id, newConfig);
    }
  };

  // Find active crop coordinate for current playback time
  const currentCrop = React.useMemo(() => {
    if (!trajectory || trajectory.length === 0) return null;
    let closest = trajectory[0];
    let minDiff = Math.abs(closest.timestamp_seconds - currentTime);
    for (const c of trajectory) {
      const diff = Math.abs(c.timestamp_seconds - currentTime);
      if (diff < minDiff) {
        minDiff = diff;
        closest = c;
      }
    }
    return closest;
  }, [trajectory, currentTime]);

  useEffect(() => {
    if (onCropChange) {
      onCropChange(currentCrop);
    }
  }, [currentCrop]);

  // Trigger Visual AI Analysis
  const handleStartAnalysis = async () => {
    if (!videoId) return;
    setIsAnalyzing(true);
    setError(null);
    setJobProgress(0);
    setJobStage('Enqueuing visual AI task...');

    try {
      const res = await api.startVisualAnalysis(videoId, {
        sampling_fps: reframeConfig.sampling_fps,
        confidence_threshold: reframeConfig.face_confidence_threshold,
      });

      setActiveJobId(res.job_id);

      // Poll job progress
      const pollTimer = setInterval(async () => {
        try {
          const job = await api.getJob(res.job_id);
          setJobProgress(job.progress_percent);
          setJobStage(job.stage_description || 'Processing frames...');

          if (job.status === 'completed') {
            clearInterval(pollTimer);
            setIsAnalyzing(false);
            setActiveJobId(null);
            await loadAnalysis();
          } else if (job.status === 'failed' || job.status === 'cancelled') {
            clearInterval(pollTimer);
            setIsAnalyzing(false);
            setActiveJobId(null);
            setError(job.error_message || 'Visual analysis job failed');
          }
        } catch (pollErr) {
          console.warn('Polling error:', pollErr);
        }
      }, 1200);
    } catch (e: any) {
      setIsAnalyzing(false);
      setError(e.message || 'Failed to start visual analysis');
    }
  };

  // Add Manual Crop Adjustment at currentTime
  const handleAddManualCrop = async () => {
    if (!analysis || !currentCrop) return;
    try {
      await api.addManualCrop(analysis.id, {
        timestamp_seconds: roundTime(currentTime),
        crop_x: currentCrop.crop_x,
        crop_y: currentCrop.crop_y,
        crop_width: currentCrop.crop_width,
        crop_height: currentCrop.crop_height,
      });
      await loadAnalysis();
    } catch (e: any) {
      console.warn('Failed to add manual crop:', e);
    }
  };

  const roundTime = (t: number) => Math.round(t * 100) / 100;

  return (
    <div className="flex flex-col h-full bg-surface-base border-l border-border-base overflow-y-auto">
      {/* Header */}
      <div className="p-4 border-b border-border-base flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-primary" />
          <h3 className="font-semibold text-sm text-text-primary">Visual AI & Smart Reframe</h3>
        </div>
        {analysis && (
          <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            {analysis.scene_type.replace('_', ' ').toUpperCase()}
          </span>
        )}
      </div>

      <div className="p-4 space-y-5">
        {/* Error message */}
        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-xs">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <div>
              <div className="font-semibold">Analysis Error</div>
              <div className="text-[11px] opacity-90">{error}</div>
            </div>
          </div>
        )}

        {/* Action: Run Visual Analysis */}
        {!analysis && !isAnalyzing && (
          <div className="p-4 rounded-xl border border-dashed border-border-muted bg-surface-muted/30 text-center space-y-3">
            <Camera className="w-8 h-8 text-primary/70 mx-auto" />
            <div>
              <h4 className="font-semibold text-xs text-text-primary">No Visual Analysis Yet</h4>
              <p className="text-[11px] text-text-muted mt-1">
                Scan video frames with OpenCV YuNet neural network to detect speakers, track faces, and calculate
                cinematic camera reframing.
              </p>
            </div>
            <button
              onClick={handleStartAnalysis}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-black font-semibold text-xs rounded-lg transition-all shadow-md"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Run Visual AI Scan</span>
            </button>
          </div>
        )}

        {/* Progress Card */}
        {isAnalyzing && (
          <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 space-y-3">
            <div className="flex items-center justify-between text-xs font-medium">
              <span className="flex items-center gap-2 text-text-primary">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                <span>Scanning Video Frames</span>
              </span>
              <span className="font-mono text-primary font-bold">{jobProgress}%</span>
            </div>
            <div className="w-full h-1.5 bg-surface-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${jobProgress}%` }}
              />
            </div>
            <div className="text-[11px] text-text-muted italic">{jobStage}</div>
          </div>
        )}

        {/* Existing Analysis Details & Controls */}
        {analysis && (
          <>
            {/* Live Vertical Reframe Viewport */}
            <CropPreview
              videoSrc={videoSrc}
              currentTime={currentTime}
              currentCrop={currentCrop}
              aspectRatio={reframeConfig.aspect_ratio}
            />

            {/* Scene Composition Summary */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-lg border border-border-muted bg-surface-muted/30">
                <div className="text-text-muted text-[10px]">Identified Tracks</div>
                <div className="text-sm font-semibold text-text-primary mt-0.5">
                  {analysis.tracks?.length || 0} Subjects
                </div>
              </div>
              <div className="p-2.5 rounded-lg border border-border-muted bg-surface-muted/30">
                <div className="text-text-muted text-[10px]">Face Presence</div>
                <div className="text-sm font-semibold text-text-primary mt-0.5">
                  {analysis.total_frames_sampled > 0
                    ? Math.round((analysis.frames_with_faces / analysis.total_frames_sampled) * 100)
                    : 0}
                  % of frames
                </div>
              </div>
            </div>

            {/* Reframe Controls */}
            <div className="pt-2">
              <ReframeSettingsPanel
                config={reframeConfig}
                onChange={handleConfigChange}
                tracks={analysis.tracks || []}
              />
            </div>

            {/* Manual Keyframe Crop Adjustment */}
            <div className="pt-3 border-t border-border-base space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                  Manual Adjustments
                </span>
                <span className="text-[11px] text-text-muted font-mono">{roundTime(currentTime)}s</span>
              </div>
              <button
                onClick={handleAddManualCrop}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg border border-border-muted bg-surface-muted hover:border-primary/50 text-text-secondary text-xs transition-colors"
              >
                <Layers className="w-3.5 h-3.5 text-primary" />
                <span>Save Keyframe Crop at Current Position</span>
              </button>
            </div>

            {/* Re-run button */}
            <div className="pt-3 border-t border-border-base">
              <button
                onClick={handleStartAnalysis}
                disabled={isAnalyzing}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg border border-border-muted text-text-muted hover:text-text-primary text-xs transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Re-scan Video AI</span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
