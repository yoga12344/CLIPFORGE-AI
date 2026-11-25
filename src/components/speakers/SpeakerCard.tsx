import React, { useState } from 'react';
import { User, Check, Edit2, Video, Eye, EyeOff, ShieldCheck, Sparkles } from 'lucide-react';
import { SpeakerData, SpeakerFaceMatchData } from '../../services/api';

interface SpeakerCardProps {
  speaker: SpeakerData;
  totalSpeechDuration: number;
  onUpdateSpeaker: (speakerId: string, updates: { display_name?: string; color?: string }) => Promise<void>;
  association?: SpeakerFaceMatchData | null;
  availableFaceTracks?: string[];
  onUpdateAssociation?: (speakerId: string, faceTrackId: string | null, isOffScreen: boolean) => Promise<void>;
  isSelected?: boolean;
  onClick?: () => void;
}

export const SpeakerCard: React.FC<SpeakerCardProps> = ({
  speaker,
  totalSpeechDuration,
  onUpdateSpeaker,
  association,
  availableFaceTracks = [],
  onUpdateAssociation,
  isSelected,
  onClick,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [nameInput, setNameInput] = useState(speaker.display_name || speaker.label);
  const [isSaving, setIsSaving] = useState(false);
  const [isUpdatingAssoc, setIsUpdatingAssoc] = useState(false);

  const percentage = totalSpeechDuration > 0
    ? Math.round((speaker.total_speech_duration / totalSpeechDuration) * 100)
    : 0;

  const handleSave = async (e: React.FormEvent) => {
    e.stopPropagation();
    if (!nameInput.trim()) return;
    setIsSaving(true);
    try {
      await onUpdateSpeaker(speaker.id, { display_name: nameInput.trim() });
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to update speaker name:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleFaceSelect = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    e.stopPropagation();
    if (!onUpdateAssociation) return;
    const value = e.target.value;
    setIsUpdatingAssoc(true);
    try {
      if (value === 'off_screen') {
        await onUpdateAssociation(speaker.id, null, true);
      } else if (value === 'none') {
        await onUpdateAssociation(speaker.id, null, false);
      } else {
        await onUpdateAssociation(speaker.id, value, false);
      }
    } catch (err) {
      console.error('Failed to update face association:', err);
    } finally {
      setIsUpdatingAssoc(false);
    }
  };

  const formatSeconds = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const remainingSec = Math.floor(sec % 60);
    return `${mins}m ${remainingSec}s`;
  };

  const color = speaker.color || '#6366f1';

  return (
    <div
      onClick={onClick}
      className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
        isSelected
          ? 'bg-zinc-800/90 border-indigo-500 shadow-md shadow-indigo-500/10'
          : 'bg-zinc-900/70 border-zinc-800/80 hover:bg-zinc-800/50 hover:border-zinc-700'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white shrink-0 shadow-inner"
            style={{ backgroundColor: color }}
          >
            <User className="w-4 h-4" />
          </div>

          <div className="min-w-0">
            {isEditing ? (
              <form onSubmit={handleSave} className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                <input
                  type="text"
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  autoFocus
                  className="bg-zinc-950 border border-zinc-700 rounded px-2 py-0.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
                <button
                  type="submit"
                  disabled={isSaving}
                  className="p-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50"
                >
                  <Check className="w-3 h-3" />
                </button>
              </form>
            ) : (
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-zinc-100 truncate">
                  {speaker.display_name || speaker.label}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsEditing(true);
                  }}
                  className="p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
                  title="Rename speaker"
                >
                  <Edit2 className="w-3 h-3" />
                </button>
              </div>
            )}
            <span className="text-[10px] text-zinc-500 block">
              {speaker.speaker_identifier || 'Unknown ID'}
            </span>
          </div>
        </div>

        <div className="text-right shrink-0">
          <div className="text-xs font-semibold text-zinc-200">
            {formatSeconds(speaker.total_speech_duration)}
          </div>
          <div className="text-[10px] text-zinc-400">
            {percentage}% speech · {speaker.turn_count} turns
          </div>
        </div>
      </div>

      {/* Concept B Audio-Visual Face Association Badge & Controls */}
      <div className="mt-2.5 pt-2 border-t border-zinc-800/60 flex items-center justify-between gap-2 text-[11px]">
        <div className="flex items-center gap-1.5 min-w-0">
          {association?.is_off_screen ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px] font-medium">
              <EyeOff className="w-3 h-3 text-zinc-500" />
              Off-Screen Speaker
            </span>
          ) : association?.face_track_id ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-950/80 border border-indigo-700/50 text-indigo-300 text-[10px] font-medium">
              <Video className="w-3 h-3 text-indigo-400" />
              Face: {association.face_track_id}
              {association.status === 'confirmed' && (
                <ShieldCheck className="w-3 h-3 text-emerald-400 ml-0.5" title="Confirmed multi-turn match" />
              )}
            </span>
          ) : (
            <span className="text-[10px] text-zinc-500 italic">No face match</span>
          )}

          {association && !association.is_off_screen && association.face_track_id && (
            <span className="text-[10px] text-zinc-400 font-mono">
              {Math.round(association.confidence * 100)}%
            </span>
          )}

          {association?.is_manual && (
            <span className="text-[9px] px-1 py-0.2 rounded bg-amber-950 text-amber-400 border border-amber-800/50">
              Manual
            </span>
          )}
        </div>

        {/* Manual Association Dropdown */}
        {onUpdateAssociation && (
          <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
            <select
              value={association?.is_off_screen ? 'off_screen' : (association?.face_track_id || 'none')}
              onChange={handleFaceSelect}
              disabled={isUpdatingAssoc}
              className="bg-zinc-950 border border-zinc-700 hover:border-zinc-600 rounded px-1.5 py-0.5 text-[10px] text-zinc-300 focus:outline-none focus:border-indigo-500 transition-colors"
            >
              <option value="none">Auto Match</option>
              {availableFaceTracks.map((fId) => (
                <option key={fId} value={fId}>
                  Face {fId}
                </option>
              ))}
              <option value="off_screen">Off-Screen</option>
            </select>
          </div>
        )}
      </div>

      {/* Progress Bar of speech share */}
      <div className="mt-2.5 w-full bg-zinc-950/60 h-1.5 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.max(percentage, 2)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
};
