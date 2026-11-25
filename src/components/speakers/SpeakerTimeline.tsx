import React, { useRef } from 'react';
import { SpeakerData, SpeakerTurnData, ActiveSpeakerSegmentData } from '../../services/api';
import { Video, Mic } from 'lucide-react';

interface SpeakerTimelineProps {
  turns: SpeakerTurnData[];
  speakers: SpeakerData[];
  activeSegments?: ActiveSpeakerSegmentData[];
  totalDuration: number;
  currentTime: number;
  onSeek: (time: number) => void;
  selectedSpeakerId?: string | null;
  className?: string;
}

export const SpeakerTimeline: React.FC<SpeakerTimelineProps> = ({
  turns,
  speakers,
  activeSegments = [],
  totalDuration,
  currentTime,
  onSeek,
  selectedSpeakerId,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const speakerColorMap = new Map<string, string>();
  speakers.forEach((s) => {
    if (s.id && s.color) speakerColorMap.set(s.id, s.color);
    if (s.speaker_identifier && s.color) speakerColorMap.set(s.speaker_identifier, s.color);
  });

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current || totalDuration <= 0) return;
    const rect = containerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const progress = Math.max(0, Math.min(1, clickX / rect.width));
    onSeek(progress * totalDuration);
  };

  const playheadPercent = totalDuration > 0
    ? Math.max(0, Math.min(100, (currentTime / totalDuration) * 100))
    : 0;

  const formatTimestamp = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${mins}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center justify-between text-[11px] text-zinc-400 font-medium">
        <span>0:00</span>
        <div className="flex items-center gap-3 text-zinc-400 text-[10px]">
          <span className="flex items-center gap-1">
            <Mic className="w-3 h-3 text-indigo-400" /> Acoustic Diarization
          </span>
          {activeSegments.length > 0 && (
            <span className="flex items-center gap-1">
              <Video className="w-3 h-3 text-emerald-400" /> Active Face Tracks
            </span>
          )}
        </div>
        <span>{formatTimestamp(totalDuration)}</span>
      </div>

      <div
        ref={containerRef}
        onClick={handleTimelineClick}
        className="relative h-14 w-full bg-zinc-950/80 rounded-xl border border-zinc-800/80 overflow-hidden cursor-pointer select-none group flex flex-col justify-between py-1"
      >
        {/* Lane 1: Acoustic Diarization Turns */}
        <div className="relative h-5 w-full">
          {turns.map((turn) => {
            if (totalDuration <= 0) return null;
            const leftPercent = (turn.start_time / totalDuration) * 100;
            const widthPercent = Math.max(0.4, (turn.duration / totalDuration) * 100);

            const isDimmed = selectedSpeakerId && turn.speaker_id !== selectedSpeakerId;
            const color = turn.speaker_id
              ? speakerColorMap.get(turn.speaker_id) || turn.color || '#6366f1'
              : '#71717a';

            return (
              <div
                key={turn.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onSeek(turn.start_time);
                }}
                style={{
                  left: `${leftPercent}%`,
                  width: `${widthPercent}%`,
                  backgroundColor: color,
                }}
                className={`absolute top-0.5 bottom-0.5 rounded-sm transition-opacity hover:opacity-100 ${
                  isDimmed ? 'opacity-25' : 'opacity-85'
                }`}
                title={`Acoustic Turn (${turn.display_name || turn.speaker_identifier}): ${formatTimestamp(turn.start_time)} - ${formatTimestamp(turn.end_time)} (${turn.duration.toFixed(1)}s, ${Math.round(turn.confidence * 100)}% conf)`}
              />
            );
          })}
        </div>

        {/* Lane 2: Active Visible Speaker Segments (Concept A) */}
        {activeSegments.length > 0 && (
          <div className="relative h-5 w-full border-t border-zinc-900/60 pt-0.5">
            {activeSegments.map((seg, sIdx) => {
              if (totalDuration <= 0) return null;
              const leftPercent = (seg.start_time / totalDuration) * 100;
              const widthPercent = Math.max(0.4, (seg.duration / totalDuration) * 100);

              const isOffScreen = seg.face_track_id === null || seg.state === 'off_screen_speaker';
              const segColor = isOffScreen
                ? '#52525b' // zinc-600 for off-screen
                : '#10b981'; // emerald-500 for active visible face

              return (
                <div
                  key={seg.id || `act_${sIdx}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSeek(seg.start_time);
                  }}
                  style={{
                    left: `${leftPercent}%`,
                    width: `${widthPercent}%`,
                    backgroundColor: segColor,
                  }}
                  className="absolute top-0.5 bottom-0.5 rounded-sm transition-opacity opacity-80 hover:opacity-100"
                  title={`Active Speaker [${seg.face_track_id || 'Off-Screen'}]: ${formatTimestamp(seg.start_time)} - ${formatTimestamp(seg.end_time)} (${seg.duration.toFixed(1)}s, ${Math.round(seg.confidence * 100)}% conf)`}
                />
              );
            })}
          </div>
        )}

        {/* Playhead Marker */}
        <div
          style={{ left: `${playheadPercent}%` }}
          className="absolute top-0 bottom-0 w-0.5 bg-rose-500 shadow-md shadow-rose-500/50 pointer-events-none z-10"
        >
          <div className="absolute -top-1 -left-1.5 w-3.5 h-3.5 bg-rose-500 rounded-full border-2 border-zinc-950" />
        </div>
      </div>
    </div>
  );
};
