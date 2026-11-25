import React, { useState } from 'react';
import { Play, Edit3, Check, X, Clock, Sparkles } from 'lucide-react';
import { TranscriptSegmentData } from '../../services/api';
import { TranscriptWordComponent } from './TranscriptWord';

interface TranscriptSegmentProps {
  segment: TranscriptSegmentData;
  currentTime: number;
  isCurrentSegment: boolean;
  searchQuery?: string;
  onSeek: (time: number) => void;
  onSaveText: (segmentId: string, newText: string) => Promise<void>;
}

export const TranscriptSegmentComponent: React.FC<TranscriptSegmentProps> = ({
  segment,
  currentTime,
  isCurrentSegment,
  searchQuery,
  onSeek,
  onSaveText,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(segment.text);
  const [isSaving, setIsSaving] = useState(false);

  const formatTimestamp = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  const handleSave = async () => {
    if (!editText.trim()) return;
    setIsSaving(true);
    try {
      await onSaveText(segment.id, editText.trim());
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save segment:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const hasWords = segment.words && segment.words.length > 0;

  return (
    <div
      onClick={() => onSeek(segment.start_time)}
      className={`p-3 rounded-xl border transition-all cursor-pointer ${
        isCurrentSegment
          ? 'bg-zinc-850/90 border-indigo-500/80 shadow-md ring-1 ring-indigo-500/20'
          : 'bg-zinc-950/40 border-zinc-800/70 hover:border-zinc-700/80 hover:bg-zinc-900/40'
      }`}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] bg-zinc-800/80 text-zinc-300 px-1.5 py-0.5 rounded flex items-center gap-1">
            <Clock className="w-3 h-3 text-indigo-400" />
            {formatTimestamp(segment.start_time)} - {formatTimestamp(segment.end_time)}
          </span>

          {segment.confidence !== undefined && (
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                segment.confidence >= 0.8
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : segment.confidence >= 0.5
                  ? 'bg-amber-500/10 text-amber-400'
                  : 'bg-rose-500/10 text-rose-400'
              }`}
              title="Confidence Score"
            >
              {(segment.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {!isEditing ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsEditing(true);
              }}
              className="p-1 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors"
              title="Edit segment text"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
          ) : (
            <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="p-1 text-emerald-400 hover:bg-emerald-500/20 rounded transition-colors"
                title="Save"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => {
                  setEditText(segment.text);
                  setIsEditing(false);
                }}
                className="p-1 text-zinc-400 hover:bg-zinc-800 rounded transition-colors"
                title="Cancel"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      {isEditing ? (
        <div onClick={(e) => e.stopPropagation()} className="mt-1">
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-indigo-500 font-sans leading-relaxed"
            rows={2}
            autoFocus
          />
        </div>
      ) : (
        <div className="text-xs leading-relaxed">
          {hasWords ? (
            <div className="flex flex-wrap gap-x-1 gap-y-0.5">
              {segment.words!.map((w, idx) => {
                const isWordActive =
                  currentTime >= w.start && currentTime <= w.end;
                return (
                  <TranscriptWordComponent
                    key={idx}
                    word={w}
                    isActive={isWordActive}
                    onSeek={onSeek}
                  />
                );
              })}
            </div>
          ) : (
            <p className="text-zinc-200">{segment.text}</p>
          )}
        </div>
      )}
    </div>
  );
};
