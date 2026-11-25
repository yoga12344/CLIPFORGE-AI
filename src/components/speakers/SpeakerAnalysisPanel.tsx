import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Users,
  Mic,
  Play,
  RefreshCw,
  Loader2,
  AlertCircle,
  Sliders,
  CheckCircle2,
  Trash2,
  Sparkles,
  Cpu,
  Video,
} from 'lucide-react';
import {
  api,
  SpeakerData,
  SpeakerTurnData,
  DiarizationSummaryData,
  DiarizationCapabilitiesData,
  ActiveSpeakerSegmentData,
  SpeakerFaceMatchData,
} from '../../services/api';
import { SpeakerCard } from './SpeakerCard';
import { SpeakerTimeline } from './SpeakerTimeline';
import { SpeakerTurnEditor } from './SpeakerTurnEditor';

interface SpeakerAnalysisPanelProps {
  videoId: string;
  projectId: string;
  currentTime: number;
  onSeek: (time: number) => void;
  className?: string;
}

export const SpeakerAnalysisPanel: React.FC<SpeakerAnalysisPanelProps> = ({
  videoId,
  projectId,
  currentTime,
  onSeek,
  className = '',
}) => {
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [audioAnalysisStatus, setAudioAnalysisStatus] = useState<string | null>(null);
  const [videoDuration, setVideoDuration] = useState<number>(0);
  const [totalSpeechDuration, setTotalSpeechDuration] = useState<number>(0);

  const [diarization, setDiarization] = useState<DiarizationSummaryData | null>(null);
  const [speakers, setSpeakers] = useState<SpeakerData[]>([]);
  const [turns, setTurns] = useState<SpeakerTurnData[]>([]);
  const [selectedSpeakerId, setSelectedSpeakerId] = useState<string | null>(null);

  // Active Speaker & Multimodal Association (Phase 8 Stage 4)
  const [activeSegments, setActiveSegments] = useState<ActiveSpeakerSegmentData[]>([]);
  const [associations, setAssociations] = useState<SpeakerFaceMatchData[]>([]);

  const [capabilities, setCapabilities] = useState<DiarizationCapabilitiesData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [progressMsg, setProgressMsg] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Configuration controls
  const [showConfig, setShowConfig] = useState<boolean>(false);
  const [distanceThreshold, setDistanceThreshold] = useState<number>(0.65);
  const [expectedSpeakers, setExpectedSpeakers] = useState<number | null>(null);

  const availableFaceTracks = useMemo(() => {
    const trackSet = new Set<string>();
    activeSegments.forEach((s) => {
      if (s.face_track_id) trackSet.add(s.face_track_id);
    });
    associations.forEach((a) => {
      if (a.face_track_id) trackSet.add(a.face_track_id);
    });
    return Array.from(trackSet).sort();
  }, [activeSegments, associations]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      // 1. Fetch Diarization capabilities
      try {
        const caps = await api.getSpeakerCapabilities();
        setCapabilities(caps);
        if (caps.default_config) {
          setDistanceThreshold(caps.default_config.distance_threshold);
        }
      } catch (e) {
        console.warn('Failed to load speaker capabilities:', e);
      }

      // 2. Fetch latest audio analysis for this video
      try {
        const audioRes = await api.getLatestAudioAnalysis(videoId);
        if (audioRes && audioRes.id) {
          setAnalysisId(audioRes.id);
          setAudioAnalysisStatus(audioRes.status);
          setVideoDuration(audioRes.duration_seconds || 0);

          // 3. Fetch diarization results if available
          try {
            const diarSummary = await api.getDiarizationSummary(audioRes.id);
            if (diarSummary && diarSummary.speakers && diarSummary.speakers.length > 0) {
              setDiarization(diarSummary);
              setSpeakers(diarSummary.speakers);
              setTurns(diarSummary.speaker_turns || []);
              setTotalSpeechDuration(diarSummary.total_speech_duration || 0);
            } else {
              setDiarization(null);
              setSpeakers([]);
              setTurns([]);
            }
          } catch (diarErr) {
            setDiarization(null);
            setSpeakers([]);
            setTurns([]);
          }
        } else {
          setAnalysisId(null);
          setAudioAnalysisStatus(null);
        }
      } catch (err: any) {
        if (err?.message?.includes('404')) {
          setAnalysisId(null);
          setAudioAnalysisStatus(null);
        } else {
          console.warn('Error fetching audio analysis:', err);
        }
      }

      // 4. Fetch Active Speaker & Face Identity Associations
      try {
        const asdRes = await api.getVideoActiveSpeakers(videoId);
        if (asdRes) {
          setActiveSegments(asdRes.active_segments || []);
          setAssociations(asdRes.associations || []);
        }
      } catch (asdErr) {
        // Active speakers may not be computed yet; non-blocking
        setActiveSegments([]);
        setAssociations([]);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to initialize speaker analysis');
    } finally {
      setIsLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Start Voice Activity Detection if not already done
  const handleStartVAD = async () => {
    setIsProcessing(true);
    setProgressMsg('Extracting 16kHz audio and running Silero VAD...');
    setErrorMsg(null);
    try {
      const res = await api.startAudioAnalysis(videoId, true);
      const pollInterval = setInterval(async () => {
        try {
          const job = await api.getJob(res.job_id);
          if (job.status === 'completed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            setProgressMsg('');
            await loadData();
          } else if (job.status === 'failed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            setErrorMsg(job.error_message || 'Audio analysis failed');
          } else {
            setProgressMsg(job.stage_description || 'Analyzing audio...');
          }
        } catch {
          clearInterval(pollInterval);
          setIsProcessing(false);
        }
      }, 1000);
    } catch (err: any) {
      setIsProcessing(false);
      setErrorMsg(err.message || 'Failed to start audio analysis');
    }
  };

  // Start Offline Speaker Diarization
  const handleStartDiarization = async () => {
    if (!analysisId) return;
    setIsProcessing(true);
    setProgressMsg('Extracting CAM++ embeddings and clustering speakers...');
    setErrorMsg(null);
    try {
      const config = {
        distance_threshold: distanceThreshold,
        expected_speakers: expectedSpeakers || undefined,
      };
      const res = await api.startSpeakerDiarization(analysisId, config, true);

      const pollInterval = setInterval(async () => {
        try {
          const job = await api.getJob(res.job_id);
          if (job.status === 'completed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            setProgressMsg('');
            await loadData();
          } else if (job.status === 'failed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            setErrorMsg(job.error_message || 'Speaker diarization failed');
          } else {
            setProgressMsg(job.stage_description || 'Diarizing speech...');
          }
        } catch {
          clearInterval(pollInterval);
          setIsProcessing(false);
        }
      }, 1000);
    } catch (err: any) {
      setIsProcessing(false);
      setErrorMsg(err.message || 'Failed to start speaker diarization');
    }
  };

  // Update Speaker Name or Color
  const handleUpdateSpeaker = async (
    speakerId: string,
    updates: { display_name?: string; color?: string }
  ) => {
    try {
      const updated = await api.updateSpeaker(speakerId, updates);
      setSpeakers((prev) =>
        prev.map((s) => (s.id === speakerId ? { ...s, ...updated } : s))
      );
      setTurns((prev) =>
        prev.map((t) =>
          t.speaker_id === speakerId
            ? { ...t, display_name: updated.display_name, color: updated.color }
            : t
        )
      );
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update speaker');
    }
  };

  // Reassign Speaker Turn
  const handleReassignTurn = async (turnId: string, newSpeakerId: string) => {
    try {
      const updated = await api.updateSpeakerTurn(turnId, {
        speaker_id: newSpeakerId,
        assignment_status: 'manual',
      });
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, ...updated } : t))
      );
      if (analysisId) {
        const freshSummary = await api.getDiarizationSummary(analysisId);
        if (freshSummary) {
          setSpeakers(freshSummary.speakers);
          setTotalSpeechDuration(freshSummary.total_speech_duration);
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to reassign turn');
    }
  };

  // Update Speaker-to-Face Association
  const handleUpdateAssociation = async (
    speakerId: string,
    faceTrackId: string | null,
    isOffScreen: boolean
  ) => {
    try {
      const updated = await api.updateSpeakerFaceAssociation(videoId, speakerId, {
        face_track_id: faceTrackId,
        is_off_screen: isOffScreen,
      });
      setAssociations((prev) => {
        const remaining = prev.filter((a) => a.speaker_id !== speakerId);
        return [...remaining, updated];
      });
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update face association');
    }
  };

  // Clear Diarization Results
  const handleClearDiarization = async () => {
    if (!analysisId) return;
    try {
      await api.deleteDiarization(analysisId);
      setDiarization(null);
      setSpeakers([]);
      setTurns([]);
      setSelectedSpeakerId(null);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to clear diarization');
    }
  };

  if (isLoading) {
    return (
      <div className={`flex flex-col items-center justify-center p-8 bg-zinc-900 border border-zinc-800 rounded-2xl ${className}`}>
        <Loader2 className="w-6 h-6 animate-spin text-indigo-500 mb-2" />
        <span className="text-xs text-zinc-400">Loading audio intelligence...</span>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-indigo-950/60 border border-indigo-800/40 rounded-xl text-indigo-400">
            <Users className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              Speaker Diarization & Audio-Visual Intelligence
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800/50">
                Local-First
              </span>
            </h3>
            <span className="text-[11px] text-zinc-400">
              3D-Speaker CAM++ ONNX & Light-ASD Multimodal Tracking
            </span>
          </div>
        </div>

        <button
          onClick={() => setShowConfig(!showConfig)}
          className={`p-1.5 rounded-lg border transition-colors ${
            showConfig
              ? 'bg-zinc-800 border-zinc-700 text-zinc-200'
              : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'
          }`}
          title="Clustering parameters"
        >
          <Sliders className="w-4 h-4" />
        </button>
      </div>

      {/* Error Message */}
      {errorMsg && (
        <div className="m-3 p-2.5 bg-rose-950/40 border border-rose-800/50 rounded-xl flex items-center gap-2 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="truncate">{errorMsg}</span>
        </div>
      )}

      {/* Configuration Drawer */}
      {showConfig && (
        <div className="p-3 bg-zinc-950 border-b border-zinc-800 text-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-zinc-300 font-medium">Clustering Sensitivity (Cosine Threshold)</span>
            <span className="text-zinc-400 font-mono">{distanceThreshold.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min="0.30"
            max="0.95"
            step="0.05"
            value={distanceThreshold}
            onChange={(e) => setDistanceThreshold(parseFloat(e.target.value))}
            className="w-full accent-indigo-500"
          />
          <div className="flex items-center justify-between text-[10px] text-zinc-500">
            <span>More Speakers (0.30)</span>
            <span>Balanced (0.65)</span>
            <span>Fewer Speakers (0.95)</span>
          </div>
        </div>
      )}

      {/* Body Content */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {/* Step 1: No Audio Analysis / VAD Yet */}
        {!analysisId && (
          <div className="text-center py-10 space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-zinc-800/80 flex items-center justify-center text-zinc-400 mx-auto">
              <Mic className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-zinc-200">Audio Preprocessing Required</h4>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto mt-1">
                Extract 16kHz mono audio and compute voice activity boundaries before running speaker diarization.
              </p>
            </div>
            <button
              onClick={handleStartVAD}
              disabled={isProcessing}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold inline-flex items-center gap-2 shadow-lg shadow-indigo-600/20 disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{progressMsg || 'Processing Audio...'}</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Analyze Audio (Silero VAD)</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Step 2: Audio Analysis ready, but Diarization not executed */}
        {analysisId && (!diarization || speakers.length === 0) && (
          <div className="text-center py-10 space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-indigo-950/40 border border-indigo-800/40 flex items-center justify-center text-indigo-400 mx-auto">
              <Users className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-zinc-200">Voice Activity Detected</h4>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto mt-1">
                Run local CAM++ neural embeddings to identify unique speakers and create utterance turns.
              </p>
            </div>
            <button
              onClick={handleStartDiarization}
              disabled={isProcessing}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold inline-flex items-center gap-2 shadow-lg shadow-indigo-600/20 disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{progressMsg || 'Diarizing Speakers...'}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 fill-current" />
                  <span>Run Speaker Diarization</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Step 3: Diarization Complete */}
        {analysisId && diarization && speakers.length > 0 && (
          <div className="space-y-4">
            {/* Summary Metrics */}
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="p-2.5 bg-zinc-950/60 border border-zinc-800/80 rounded-xl">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Speakers</span>
                <span className="text-base font-bold text-zinc-100">{speakers.length}</span>
              </div>
              <div className="p-2.5 bg-zinc-950/60 border border-zinc-800/80 rounded-xl">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Total Speech</span>
                <span className="text-base font-bold text-zinc-100">{totalSpeechDuration.toFixed(1)}s</span>
              </div>
              <div className="p-2.5 bg-zinc-950/60 border border-zinc-800/80 rounded-xl">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Turns</span>
                <span className="text-base font-bold text-zinc-100">{turns.length}</span>
              </div>
              <div className="p-2.5 bg-zinc-950/60 border border-zinc-800/80 rounded-xl">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">Faces Matched</span>
                <span className="text-base font-bold text-zinc-100">
                  {associations.filter((a) => a.face_track_id).length}
                </span>
              </div>
            </div>

            {/* Interactive Timeline */}
            <div className="bg-zinc-950/40 p-3 rounded-2xl border border-zinc-800/80">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-zinc-300">Synchronized Multimodal Timeline</span>
                {selectedSpeakerId && (
                  <button
                    onClick={() => setSelectedSpeakerId(null)}
                    className="text-[10px] text-indigo-400 hover:underline"
                  >
                    Clear Filter
                  </button>
                )}
              </div>
              <SpeakerTimeline
                turns={turns}
                speakers={speakers}
                activeSegments={activeSegments}
                totalDuration={videoDuration}
                currentTime={currentTime}
                onSeek={onSeek}
                selectedSpeakerId={selectedSpeakerId}
              />
            </div>

            {/* Speaker Cards */}
            <div>
              <span className="text-[11px] font-semibold text-zinc-300 block mb-2">
                Recognized Speakers & Visual Associations
              </span>
              <div className="space-y-2">
                {speakers.map((spk) => {
                  const assoc = associations.find(
                    (a) => a.speaker_id === spk.id || a.speaker_id === spk.speaker_identifier
                  );
                  return (
                    <SpeakerCard
                      key={spk.id}
                      speaker={spk}
                      totalSpeechDuration={totalSpeechDuration}
                      onUpdateSpeaker={handleUpdateSpeaker}
                      association={assoc}
                      availableFaceTracks={availableFaceTracks}
                      onUpdateAssociation={handleUpdateAssociation}
                      isSelected={selectedSpeakerId === spk.id}
                      onClick={() =>
                        setSelectedSpeakerId(selectedSpeakerId === spk.id ? null : spk.id)
                      }
                    />
                  );
                })}
              </div>
            </div>

            {/* Turn Editor */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-zinc-300">Utterance Turns ({turns.length})</span>
                <span className="text-[10px] text-zinc-500">Click turn to seek & reassign</span>
              </div>
              <SpeakerTurnEditor
                turns={
                  selectedSpeakerId
                    ? turns.filter((t) => t.speaker_id === selectedSpeakerId)
                    : turns
                }
                speakers={speakers}
                currentTime={currentTime}
                onSeek={onSeek}
                onReassignTurn={handleReassignTurn}
                className="max-h-64"
              />
            </div>

            {/* Action Bar */}
            <div className="pt-2 flex items-center justify-between border-t border-zinc-800 text-xs">
              <button
                onClick={handleClearDiarization}
                className="text-zinc-500 hover:text-rose-400 inline-flex items-center gap-1 transition-colors text-[11px]"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Reset</span>
              </button>

              <button
                onClick={handleStartDiarization}
                disabled={isProcessing}
                className="text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1 transition-colors text-[11px] font-medium disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isProcessing ? 'animate-spin' : ''}`} />
                <span>Re-run Diarization</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
