import React from 'react';
import { Play, UserCheck, ShieldAlert, Sparkles, Sliders } from 'lucide-react';
import { SpeakerData, SpeakerTurnData } from '../../services/api';

interface SpeakerTurnEditorProps {
  turns: SpeakerTurnData[];
  speakers: SpeakerData[];
  currentTime: number;
  onSeek: (time: number) => void;
  onReassignTurn: (turnId: string, speakerId: string) => Promise<void>;
  className?: string;
}

export const SpeakerTurnEditor: React.FC<SpeakerTurnEditorProps> = ({
  turns,
  speakers,
  currentTime,
  onSeek,
  onReassignTurn,
  className = '',
}) => {
  const formatTimestamp = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 10);
    return `${mins}:${s < 10 ? '0' : ''}${s}.${ms}`;
  };

  const speakerColorMap = new Map<string, string>();
  speakers.forEach((s) => {
    if (s.id && s.color) speakerColorMap.set(s.id, s.color);
  });

  return (
    <div className={`space-y-2 overflow-y-auto pr-1 ${className}`}>
      {turns.length === 0 ? (
        <div className="text-center py-8 text-zinc-500 text-xs">
          No speaker turns available. Run diarization to generate speech turns.
        </div>
      ) : (
        turns.map((turn, index) => {
          const isActive = currentTime >= turn.start_time && currentTime <= turn.end_time;
          const turnColor = turn.speaker_id
            ? speakerColorMap.get(turn.speaker_id) || turn.color || '#6366f1'
            : '#71717a';

          return (
            <div
              key={turn.id || index}
              className={`p-2.5 rounded-xl border transition-all text-xs flex items-center justify-between gap-3 ${
                isActive
                  ? 'bg-zinc-800/90 border-indigo-500 shadow-md shadow-indigo-500/10'
                  : 'bg-zinc-900/60 border-zinc-800/70 hover:bg-zinc-800/40 hover:border-zinc-700/60'
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <button
                  onClick={() => onSeek(turn.start_time)}
                  className="p-1.5 rounded-lg bg-zinc-800 hover:bg-indigo-600 text-zinc-300 hover:text-white transition-colors shrink-0"
                  title="Play from turn start"
                >
                  <Play className="w-3 h-3 fill-current" />
                </button>

                <div
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: turnColor }}
                />

                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[11px] text-zinc-300">
                      {formatTimestamp(turn.start_time)} - {formatTimestamp(turn.end_time)}
                    </span>
                    <span className="text-[10px] text-zinc-500">
                      ({turn.duration.toFixed(1)}s)
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 mt-0.5">
                    {turn.assignment_status === 'manual' ? (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium text-indigo-400 bg-indigo-950/60 px-1.5 py-0.2 rounded border border-indigo-800/40">
                        <UserCheck className="w-2.5 h-2.5" />
                        Manual
                      </span>
                    ) : turn.assignment_status === 'provisional' ? (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium text-amber-400 bg-amber-950/60 px-1.5 py-0.2 rounded border border-amber-800/40">
                        <ShieldAlert className="w-2.5 h-2.5" />
                        Provisional
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-0.5 text-[9px] font-medium text-emerald-400 bg-emerald-950/60 px-1.5 py-0.2 rounded border border-emerald-800/40">
                        <Sparkles className="w-2.5 h-2.5" />
                        Auto
                      </span>
                    )}

                    <span className="text-[10px] text-zinc-500">
                      {Math.round(turn.confidence * 100)}% conf
                    </span>
                  </div>
                </div>
              </div>

              {/* Speaker Reassignment Dropdown */}
              <div className="shrink-0">
                <select
                  value={turn.speaker_id || ''}
                  onChange={(e) => onReassignTurn(turn.id, e.target.value)}
                  className="bg-zinc-950 border border-zinc-700/80 rounded-lg px-2 py-1 text-[11px] text-zinc-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="" disabled>Select Speaker</option>
                  {speakers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.display_name || s.label} ({s.speaker_identifier})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
};
