import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  FileText, Search, Copy, Check, RotateCcw, 
  Sparkles, Globe, Cpu, Clock, AlertCircle, Loader2 
} from 'lucide-react';
import { api, TranscriptData, TranscriptSegmentData } from '../../services/api';
import { TranscriptSegmentComponent } from './TranscriptSegment';
import { TranscriptSearch } from './TranscriptSearch';
import { TranscriptionSettingsModal } from './TranscriptionSettings';

interface TranscriptPanelProps {
  videoId: string;
  currentTime: number;
  onSeek: (time: number) => void;
  className?: string;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  videoId,
  currentTime,
  onSeek,
  className = '',
}) => {
  const [transcript, setTranscript] = useState<TranscriptData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const activeSegmentRef = useRef<HTMLDivElement | null>(null);

  const loadTranscript = async () => {
    setIsLoading(true);
    try {
      const data = await api.getVideoTranscript(videoId);
      setTranscript(data);
    } catch (e) {
      setTranscript(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTranscript();
  }, [videoId]);

  // Handle segment text updates
  const handleSaveSegmentText = async (segmentId: string, newText: string) => {
    try {
      const updated = await api.updateSegmentText(segmentId, newText);
      setTranscript((prev) => {
        if (!prev) return null;
        const newSegments = prev.segments.map((s) =>
          s.id === segmentId ? { ...s, text: updated.text } : s
        );
        return {
          ...prev,
          full_text: newSegments.map((s) => s.text).join(' '),
          segments: newSegments,
        };
      });
    } catch (e) {
      console.error('Failed to update segment:', e);
    }
  };

  // Filter segments based on search
  const filteredSegments = useMemo(() => {
    if (!transcript || !searchQuery.trim()) return transcript?.segments || [];
    const q = searchQuery.toLowerCase();
    return transcript.segments.filter((s) => s.text.toLowerCase().includes(q));
  }, [transcript, searchQuery]);

  const handleCopyFullText = () => {
    if (!transcript?.full_text) return;
    navigator.clipboard.writeText(transcript.full_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleStartTranscription = async (config: any) => {
    setIsTranscribing(true);
    try {
      await api.transcribeVideo(videoId, config);
      // Wait and poll or let user watch job queue
    } catch (e) {
      console.error('Transcription error:', e);
    } finally {
      setIsTranscribing(false);
    }
  };

  return (
    <div className={`bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col h-full shadow-lg ${className}`}>
      {/* Top Header */}
      <div className="p-3.5 border-b border-zinc-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-white">Transcript</h3>
          {transcript && (
            <span className="text-[11px] font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded-full">
              {transcript.segments.length} segments
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {transcript && (
            <>
              <button
                onClick={handleCopyFullText}
                className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
                title="Copy full transcript"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>

              <button
                onClick={() => setIsSettingsOpen(true)}
                className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
                title="Retranscribe"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </>
          )}

          {!transcript && (
            <button
              onClick={() => setIsSettingsOpen(true)}
              disabled={isTranscribing}
              className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 shadow-sm shadow-indigo-600/20 disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Transcribe
            </button>
          )}
        </div>
      </div>

      {/* Metadata Subheader */}
      {transcript && (
        <div className="px-3.5 py-2 bg-zinc-950/60 border-b border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <Globe className="w-3 h-3 text-zinc-500" />
              Lang: <strong className="text-zinc-300 uppercase">{transcript.language}</strong>
            </span>
            <span className="flex items-center gap-1">
              <Cpu className="w-3 h-3 text-zinc-500" />
              Model: <strong className="text-zinc-300 font-mono">{transcript.model_used || 'whisper'}</strong>
            </span>
            {transcript.device_used && (
              <span className="text-zinc-500 font-mono">
                [{transcript.device_used}]
              </span>
            )}
          </div>
        </div>
      )}

      {/* Search Bar */}
      {transcript && (
        <div className="p-2.5 border-b border-zinc-800/80">
          <TranscriptSearch
            query={searchQuery}
            onQueryChange={setSearchQuery}
            matchCount={filteredSegments.length}
            currentMatchIndex={currentMatchIndex}
            onNextMatch={() => {
              if (filteredSegments.length > 0) {
                setCurrentMatchIndex((prev) => (prev + 1) % filteredSegments.length);
              }
            }}
            onPrevMatch={() => {
              if (filteredSegments.length > 0) {
                setCurrentMatchIndex((prev) => (prev - 1 + filteredSegments.length) % filteredSegments.length);
              }
            }}
          />
        </div>
      )}

      {/* Segments Scroll Area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-3 space-y-2.5 scrollbar-thin scrollbar-thumb-zinc-700"
      >
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500 text-xs py-12">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-400 mb-2" />
            Loading transcript...
          </div>
        ) : !transcript ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-6 text-zinc-500 py-12">
            <FileText className="w-10 h-10 text-zinc-700 mb-3" />
            <h4 className="text-sm font-semibold text-zinc-300">No Transcript Yet</h4>
            <p className="text-xs text-zinc-400 mt-1 max-w-xs mb-4">
              Transcribe this video using local Whisper AI models to enable word-level seeking, subtitle export, and AI clip highlights.
            </p>
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-lg shadow-indigo-600/20"
            >
              <Sparkles className="w-4 h-4" /> Start AI Transcription
            </button>
          </div>
        ) : filteredSegments.length === 0 ? (
          <div className="text-center py-8 text-zinc-500 text-xs">
            No segments match your search query "{searchQuery}".
          </div>
        ) : (
          filteredSegments.map((segment) => {
            const isCurrent =
              currentTime >= segment.start_time && currentTime <= segment.end_time;
            return (
              <div key={segment.id} ref={isCurrent ? activeSegmentRef : null}>
                <TranscriptSegmentComponent
                  segment={segment}
                  currentTime={currentTime}
                  isCurrentSegment={isCurrent}
                  searchQuery={searchQuery}
                  onSeek={onSeek}
                  onSaveText={handleSaveSegmentText}
                />
              </div>
            );
          })
        )}
      </div>

      {/* Transcription Modal */}
      <TranscriptionSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => {
          setIsSettingsOpen(false);
          loadTranscript();
        }}
        onStartTranscription={handleStartTranscription}
        isRetranscribe={!!transcript}
      />
    </div>
  );
};
