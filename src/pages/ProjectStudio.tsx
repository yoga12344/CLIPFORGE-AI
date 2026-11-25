import React, { useEffect, useState } from 'react';
import { 
  ArrowLeft, Film, Scissors, Plus, Play, Trash2, 
  Sparkles, Check, AlertCircle, Loader2, Clock, 
  Layers, Ratio, Video as VideoIcon, FileText, Eye, Type, Users
} from 'lucide-react';
import { api, ProjectData, VideoData, ClipData, CropCoordinateData, TrackedFaceData, CaptionPresetData, SubtitleTrackData, HighlightCandidateData } from '../services/api';
import { VideoPlayer } from '../components/video/VideoPlayer';
import { ThumbnailStrip } from '../components/video/ThumbnailStrip';
import { VideoMetadataCard } from '../components/video/VideoMetadataCard';
import { JobQueue } from '../components/jobs/JobQueue';
import { TranscriptPanel } from '../components/transcript/TranscriptPanel';
import { HighlightAnalysisPanel } from '../components/highlights/HighlightAnalysisPanel';
import { VisionAnalysisPanel } from '../components/vision/VisionAnalysisPanel';
import { FaceDetectionOverlay } from '../components/vision/FaceDetectionOverlay';
import { SubtitlePanel } from '../components/subtitles/SubtitlePanel';
import { SubtitlePreviewOverlay } from '../components/subtitles/SubtitlePreviewOverlay';
import { SpeakerAnalysisPanel } from '../components/speakers/SpeakerAnalysisPanel';
import { Modal } from '../components/ui/Modal';

interface ProjectStudioProps {
  projectId: string;
  onBack: () => void;
  onNavigateToImport: () => void;
}

export const ProjectStudio: React.FC<ProjectStudioProps> = ({
  projectId,
  onBack,
  onNavigateToImport,
}) => {
  const [project, setProject] = useState<ProjectData | null>(null);
  const [videos, setVideos] = useState<VideoData[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoData | null>(null);
  const [clips, setClips] = useState<ClipData[]>([]);
  const [candidates, setCandidates] = useState<HighlightCandidateData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Player state
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const [seekTime, setSeekTime] = useState<number | undefined>(undefined);

  // Right sidebar tab state
  const [activeRightTab, setActiveRightTab] = useState<'highlights' | 'transcript' | 'vision' | 'subtitles' | 'speakers' | 'jobs'>('highlights');

  // Selected clip for editing subtitles / export
  const [selectedClip, setSelectedClip] = useState<ClipData | null>(null);
  const [activeSubtitleTrack, setActiveSubtitleTrack] = useState<SubtitleTrackData | null>(null);
  const [activeCaptionPreset, setActiveCaptionPreset] = useState<CaptionPresetData | undefined>(undefined);

  // Vision tracking states
  const [currentCrop, setCurrentCrop] = useState<CropCoordinateData | null>(null);
  const [visionTracks, setVisionTracks] = useState<TrackedFaceData[]>([]);

  // Clip Generator Modal
  const [isClipModalOpen, setIsClipModalOpen] = useState(false);
  const [clipTitle, setClipTitle] = useState('Highlight Clip');
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(15);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [reframeMode, setReframeMode] = useState('center_crop');
  const [isSubmittingClip, setIsSubmittingClip] = useState(false);

  // Clip Player Modal
  const [playingClip, setPlayingClip] = useState<ClipData | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const proj = await api.getProject(projectId);
      setProject(proj);

      // Fetch clips
      const cl = await api.listProjectClips(projectId);
      setClips(cl);

      // Fetch videos for this project using dedicated video listing
      const vids = await api.listAllVideos(projectId);
      setVideos(vids);
      if (vids && vids.length > 0) {
        if (!selectedVideo || !vids.some((v) => v.id === selectedVideo.id)) {
          setSelectedVideo(vids[0]);
          setVideoDuration(vids[0].duration_seconds);
        }
      }

      // Fetch highlight candidates for this project
      try {
        const cands = await api.listProjectHighlights(projectId);
        setCandidates(cands);
      } catch (candErr) {
        console.warn('Failed to load project highlights:', candErr);
      }
    } catch (e) {
      console.warn('Failed to load project studio:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [projectId]);

  const handleTimeUpdate = (curr: number, dur: number) => {
    setCurrentTime(curr);
    if (dur > 0 && videoDuration === 0) {
      setVideoDuration(dur);
    }
  };

  const handleGeneratePreview = async () => {
    if (!selectedVideo) return;
    try {
      await api.generateVideoPreview(selectedVideo.id);
    } catch (e) {
      console.error(e);
    }
  };

  const handleExtractAudio = async () => {
    if (!selectedVideo) return;
    try {
      await api.extractVideoAudio(selectedVideo.id);
    } catch (e) {
      console.error(e);
    }
  };

  const handleGenerateThumbnails = async () => {
    if (!selectedVideo) return;
    try {
      await api.generateVideoThumbnail(selectedVideo.id);
    } catch (e) {
      console.error(e);
    }
  };

  const handleInspect = async () => {
    if (!selectedVideo) return;
    try {
      await api.inspectVideo(selectedVideo.id);
      await loadData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateClip = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVideo) return;
    setIsSubmittingClip(true);
    try {
      await api.generateClip({
        project_id: projectId,
        video_id: selectedVideo.id,
        title: clipTitle.trim() || 'Untitled Clip',
        start_time: startTime,
        end_time: endTime,
        aspect_ratio: aspectRatio,
        reframe_mode: reframeMode,
      });
      setIsClipModalOpen(false);
      await loadData();
    } catch (err) {
      console.error('Clip generation error:', err);
    } finally {
      setIsSubmittingClip(false);
    }
  };

  const handleDeleteClip = async (clipId: string) => {
    try {
      await api.deleteClip(clipId);
      setClips((prev) => prev.filter((c) => c.id !== clipId));
    } catch (e) {
      console.error('Delete clip error:', e);
    }
  };

  if (isLoading && !project) {
    return (
      <div className="flex items-center justify-center h-full min-h-[500px]">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 hover:bg-zinc-800 text-zinc-400 hover:text-white rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              {project?.name || 'Project Studio'}
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">
              {project?.description || 'Video processing and clip generation workspace.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {selectedVideo && (
            <button
              onClick={() => {
                setStartTime(Math.max(0, Math.floor(currentTime)));
                setEndTime(Math.min(Math.floor(videoDuration || 60), Math.floor(currentTime + 30)));
                setIsClipModalOpen(true);
              }}
              className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-2"
            >
              <Scissors className="w-4 h-4" />
              Create Short Clip
            </button>
          )}

          <button
            onClick={onNavigateToImport}
            className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" /> Import Video
          </button>
        </div>
      </div>

      {videos.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-12 text-center max-w-lg mx-auto my-12">
          <VideoIcon className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
          <h3 className="text-white font-semibold text-sm">No Videos Imported Yet</h3>
          <p className="text-zinc-400 text-xs mt-1 mb-5">
            Import a long-form video into this project to begin transcription, AI analysis, and clip generation.
          </p>
          <button
            onClick={onNavigateToImport}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition-colors inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Import Video Now
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Video & Playback Column (2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            {selectedVideo && (
              <>
                <VideoPlayer
                  src={api.getVideoPreviewUrl(selectedVideo.id)}
                  poster={selectedVideo.thumbnail_path ? api.getVideoThumbnailUrl(selectedVideo.id) : undefined}
                  onTimeUpdate={handleTimeUpdate}
                  seekTime={seekTime}
                >
                  <FaceDetectionOverlay
                    currentTime={currentTime}
                    tracks={visionTracks}
                    currentCrop={currentCrop}
                    showFaces={activeRightTab === 'vision'}
                    showCropBox={activeRightTab === 'vision'}
                  />
                  <SubtitlePreviewOverlay
                    segments={activeSubtitleTrack?.segments || []}
                    preset={activeCaptionPreset}
                    currentTime={
                      selectedClip
                        ? Math.max(0, currentTime - selectedClip.start_time)
                        : currentTime
                    }
                    isEnabled={activeSubtitleTrack?.is_enabled ?? true}
                  />
                </VideoPlayer>

                <VideoMetadataCard
                  video={selectedVideo}
                  onGeneratePreview={handleGeneratePreview}
                  onExtractAudio={handleExtractAudio}
                  onGenerateThumbnail={handleGenerateThumbnails}
                  onInspect={handleInspect}
                />
              </>
            )}

            {/* AI Discovered Highlight Candidates Section */}
            {candidates.length > 0 && (
              <div className="bg-zinc-900 border border-indigo-900/40 rounded-xl p-5 shadow-lg">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    <h3 className="text-sm font-semibold text-white">AI Discovered Highlights ({candidates.length})</h3>
                  </div>
                  <button
                    onClick={() => setActiveRightTab('highlights')}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                  >
                    View All in Highlights Tab →
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {candidates.slice(0, 6).map((cand) => (
                    <div
                      key={cand.id}
                      className="bg-zinc-950/80 border border-zinc-800 hover:border-indigo-600/50 rounded-lg p-3 flex flex-col justify-between transition-all"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1.5">
                          <span className="text-[10px] font-mono text-indigo-300 bg-indigo-950/80 border border-indigo-800/60 px-1.5 py-0.5 rounded">
                            Score: {cand.overall_score}
                          </span>
                          <span className="text-[10px] font-mono text-zinc-400">
                            {cand.start_time.toFixed(1)}s - {cand.end_time.toFixed(1)}s ({cand.duration_seconds.toFixed(0)}s)
                          </span>
                        </div>
                        <h4 className="text-xs font-semibold text-white truncate" title={cand.title}>
                          {cand.title}
                        </h4>
                        {cand.hook && (
                          <p className="text-[11px] text-zinc-400 italic line-clamp-2 mt-1">
                            "{cand.hook}"
                          </p>
                        )}
                      </div>

                      <div className="flex items-center justify-between mt-3 pt-2 border-t border-zinc-800/60 text-xs">
                        <button
                          onClick={() => setSeekTime(cand.start_time)}
                          className="text-[11px] text-zinc-400 hover:text-white flex items-center gap-1"
                        >
                          <Play className="w-3 h-3" /> Preview
                        </button>
                        <button
                          onClick={async () => {
                            try {
                              await api.createClipFromHighlight(cand.id, {
                                aspect_ratio: '9:16',
                                reframe_mode: 'center_crop',
                              });
                              await loadData();
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                          className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-semibold rounded flex items-center gap-1"
                        >
                          <Scissors className="w-3 h-3" /> Create Clip
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Generated Clips Section */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Scissors className="w-4 h-4 text-indigo-400" />
                  <h3 className="text-sm font-semibold text-white">Generated Clips ({clips.length})</h3>
                </div>
              </div>

              {clips.length === 0 ? (
                <div className="text-center py-8 text-zinc-500 text-xs">
                  No clips generated yet. Use the "Create Short Clip" button above to trim and reframe a segment.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {clips.map((clip) => (
                    <div
                      key={clip.id}
                      className="bg-zinc-950/70 border border-zinc-800 rounded-lg p-2.5 flex flex-col justify-between group hover:border-zinc-700 transition-all"
                    >
                      <div className="relative rounded overflow-hidden aspect-[9/16] bg-zinc-900 max-h-48 mb-2 flex items-center justify-center">
                        {clip.thumbnail_path ? (
                          <img
                            src={api.getClipThumbnailUrl(clip.id)}
                            alt={clip.title}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <Film className="w-8 h-8 text-zinc-700" />
                        )}

                        {clip.status === 'ready' && (
                          <button
                            onClick={() => setPlayingClip(clip)}
                            className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <div className="p-2.5 bg-indigo-600 rounded-full text-white shadow-lg">
                              <Play className="w-4 h-4 fill-current ml-0.5" />
                            </div>
                          </button>
                        )}

                        <span className="absolute top-1.5 left-1.5 bg-black/80 text-[10px] font-mono text-zinc-300 px-1.5 py-0.5 rounded">
                          {clip.aspect_ratio}
                        </span>

                        <span className="absolute bottom-1.5 right-1.5 bg-black/80 text-[10px] font-mono text-zinc-300 px-1.5 py-0.5 rounded">
                          {Math.round(clip.duration_seconds)}s
                        </span>
                      </div>

                      <div>
                        <h4 className="text-xs font-medium text-white truncate" title={clip.title}>
                          {clip.title}
                        </h4>
                        <div className="flex items-center justify-between mt-1 text-[11px] text-zinc-400">
                          <button
                            onClick={() => {
                              setSelectedClip(clip);
                              setActiveRightTab('subtitles');
                            }}
                            className="flex items-center gap-1 text-[11px] text-primary hover:underline font-medium"
                          >
                            <Type className="w-3 h-3" />
                            <span>Captions & Style</span>
                          </button>
                          <button
                            onClick={() => handleDeleteClip(clip.id)}
                            className="text-zinc-500 hover:text-rose-400 transition-colors p-1"
                            title="Delete clip"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Processing Queue, Transcript & Video Selector */}
          <div className="space-y-4">
            {/* Multiple videos selector if more than 1 */}
            {videos.length > 1 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                  Project Videos
                </h4>
                <div className="space-y-1.5">
                  {videos.map((v) => (
                    <button
                      key={v.id}
                      onClick={() => {
                        setSelectedVideo(v);
                        setVideoDuration(v.duration_seconds);
                      }}
                      className={`w-full text-left p-2.5 rounded-lg text-xs truncate transition-colors ${
                        selectedVideo?.id === v.id
                          ? 'bg-indigo-600 text-white font-medium'
                          : 'bg-zinc-950/60 text-zinc-300 hover:bg-zinc-800'
                      }`}
                    >
                      {v.filename}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Tab Navigation: Highlights vs Transcript vs Visual AI vs Subtitles vs Background Tasks */}
            <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 p-1.5 rounded-xl overflow-x-auto">
              <button
                onClick={() => setActiveRightTab('highlights')}
                className={`flex-1 flex items-center justify-center gap-1 py-2 px-1 text-xs font-semibold rounded-lg transition-all ${
                  activeRightTab === 'highlights'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 fill-current" />
                <span>Highlights</span>
              </button>
              <button
                onClick={() => setActiveRightTab('transcript')}
                className={`flex-1 flex items-center justify-center gap-1 py-2 px-1 text-xs font-semibold rounded-lg transition-all ${
                  activeRightTab === 'transcript'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Transcript</span>
              </button>
              <button
                onClick={() => setActiveRightTab('vision')}
                className={`flex-1 flex items-center justify-center gap-1 py-2 px-1 text-xs font-semibold rounded-lg transition-all ${
                  activeRightTab === 'vision'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Vision</span>
              </button>
              <button
                onClick={() => setActiveRightTab('subtitles')}
                className={`flex-1 flex items-center justify-center gap-1 py-2 px-1 text-xs font-semibold rounded-lg transition-all ${
                  activeRightTab === 'subtitles'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }`}
              >
                <Type className="w-3.5 h-3.5" />
                <span>Subtitles</span>
              </button>
              <button
                onClick={() => setActiveRightTab('speakers')}
                className={`flex-1 flex items-center justify-center gap-1 py-2 px-1 text-xs font-semibold rounded-lg transition-all ${
                  activeRightTab === 'speakers'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }`}
              >
                <Users className="w-3.5 h-3.5" />
                <span>Speakers</span>
              </button>
              <button
                onClick={() => setActiveRightTab('jobs')}
                className={`flex-1 flex items-center justify-center gap-1 py-2 px-1 text-xs font-semibold rounded-lg transition-all ${
                  activeRightTab === 'jobs'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>Tasks</span>
              </button>
            </div>

            {/* Tab Content */}
            {activeRightTab === 'highlights' && selectedVideo && (
              <HighlightAnalysisPanel
                videoId={selectedVideo.id}
                projectId={projectId}
                currentTime={currentTime}
                onSeek={(time) => setSeekTime(time)}
                className="min-h-[580px] max-h-[750px]"
                onClipCreated={loadData}
              />
            )}

            {activeRightTab === 'transcript' && selectedVideo && (
              <TranscriptPanel
                videoId={selectedVideo.id}
                currentTime={currentTime}
                onSeek={(time) => setSeekTime(time)}
                className="min-h-[580px] max-h-[750px]"
              />
            )}

            {activeRightTab === 'vision' && selectedVideo && (
              <VisionAnalysisPanel
                videoId={selectedVideo.id}
                projectId={projectId}
                currentTime={currentTime}
                videoDuration={videoDuration}
                videoSrc={api.getVideoPreviewUrl(selectedVideo.id)}
                onSeek={(time) => setSeekTime(time)}
                onCropChange={(crop) => setCurrentCrop(crop)}
                onTracksChange={(tracks) => setVisionTracks(tracks)}
              />
            )}

            {activeRightTab === 'subtitles' && (
              <SubtitlePanel
                clip={selectedClip || clips[0] || null}
                onSubtitleTrackChange={(track) => setActiveSubtitleTrack(track)}
                onPresetChange={(preset) => setActiveCaptionPreset(preset)}
                className="min-h-[580px] max-h-[750px]"
              />
            )}

            {activeRightTab === 'speakers' && selectedVideo && (
              <SpeakerAnalysisPanel
                videoId={selectedVideo.id}
                projectId={projectId}
                currentTime={currentTime}
                onSeek={(time) => setSeekTime(time)}
                className="min-h-[580px] max-h-[750px]"
              />
            )}

            {activeRightTab === 'jobs' && (
              <JobQueue projectId={projectId} />
            )}
          </div>
        </div>
      )}

      {/* Modal: Create Short Clip */}
      <Modal
        isOpen={isClipModalOpen}
        onClose={() => setIsClipModalOpen(false)}
        title="Generate Short Clip"
      >
        <form onSubmit={handleCreateClip} className="space-y-4 text-xs">
          <div>
            <label className="block text-zinc-300 font-medium mb-1">Clip Title</label>
            <input
              type="text"
              value={clipTitle}
              onChange={(e) => setClipTitle(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
              placeholder="e.g. The Key Hook Moment"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-zinc-300 font-medium mb-1">Start Time (sec)</label>
              <input
                type="number"
                min={0}
                max={videoDuration}
                step={0.5}
                value={startTime}
                onChange={(e) => setStartTime(parseFloat(e.target.value) || 0)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-medium mb-1">End Time (sec)</label>
              <input
                type="number"
                min={startTime + 1}
                max={videoDuration}
                step={0.5}
                value={endTime}
                onChange={(e) => setEndTime(parseFloat(e.target.value) || 0)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-indigo-500"
                required
              />
            </div>
          </div>

          <div className="p-2.5 bg-zinc-950/80 rounded-lg border border-zinc-800 font-mono text-[11px] text-zinc-400 flex justify-between">
            <span>Clip Duration:</span>
            <span className="text-indigo-400 font-semibold">
              {Math.max(0, endTime - startTime).toFixed(1)} seconds
            </span>
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
              onClick={() => setIsClipModalOpen(false)}
              className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmittingClip || endTime <= startTime}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {isSubmittingClip && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Render Clip
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal: Preview Rendered Clip */}
      {playingClip && (
        <Modal
          isOpen={!!playingClip}
          onClose={() => setPlayingClip(null)}
          title={`Preview Clip: ${playingClip.title}`}
        >
          <div className="space-y-3">
            <VideoPlayer
              src={api.getClipStreamUrl(playingClip.id)}
              className="max-h-[480px]"
            />
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
              <span>Ratio: {playingClip.aspect_ratio}</span>
              <span>Duration: {Math.round(playingClip.duration_seconds)}s</span>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
