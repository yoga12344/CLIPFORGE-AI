import React, { useState } from 'react';
import { 
  Play, Check, X, Edit2, Scissors, ChevronDown, 
  ChevronUp, Sparkles, Quote, Clock, Film, CheckCircle2 
} from 'lucide-react';
import { HighlightCandidateData } from '../../services/api';
import { HighlightScoreBreakdown } from './HighlightScoreBreakdown';

interface HighlightCandidateCardProps {
  candidate: HighlightCandidateData;
  onPreview: (startTime: number) => void;
  onApprove: (candidateId: string) => void;
  onReject: (candidateId: string) => void;
  onEdit: (candidateId: string, startTime: number, endTime: number, title: string) => void;
  onCreateClip: (candidate: HighlightCandidateData) => void;
}

export const HighlightCandidateCard: React.FC<HighlightCandidateCardProps> = ({
  candidate,
  onPreview,
  onApprove,
  onReject,
  onEdit,
  onCreateClip,
}) => {
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(candidate.title);
  const [editStart, setEditStart] = useState(candidate.start_time);
  const [editEnd, setEditEnd] = useState(candidate.end_time);

  const getScoreBadgeColor = (score: number) => {
    if (score >= 80) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    if (score >= 65) return 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30';
    if (score >= 50) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    return 'bg-zinc-800 text-zinc-400 border-zinc-700';
  };

  const getStatusBadge = () => {
    switch (candidate.status) {
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <Check className="w-2.5 h-2.5" /> Approved
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <X className="w-2.5 h-2.5" /> Rejected
          </span>
        );
      case 'edited':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <Edit2 className="w-2.5 h-2.5" /> Edited
          </span>
        );
      case 'ready_for_render':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/20 text-purple-400 border border-purple-500/30">
            <Film className="w-2.5 h-2.5" /> Clip Rendered
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">
            Discovered
          </span>
        );
    }
  };

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    onEdit(candidate.id, editStart, editEnd, editTitle);
    setIsEditing(false);
  };

  return (
    <div
      className={`bg-zinc-900 border rounded-xl p-4 transition-all space-y-3 ${
        candidate.status === 'approved'
          ? 'border-emerald-500/40 shadow-lg shadow-emerald-500/5'
          : candidate.status === 'rejected'
          ? 'border-zinc-800/60 opacity-60'
          : 'border-zinc-800 hover:border-zinc-700 shadow-md'
      }`}
    >
      {/* Top Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {getStatusBadge()}
            <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider bg-zinc-950 px-2 py-0.5 rounded border border-zinc-800">
              {candidate.category}
            </span>
            <span className="flex items-center gap-1 text-[11px] font-mono text-zinc-400">
              <Clock className="w-3 h-3 text-zinc-500" />
              {candidate.start_time.toFixed(1)}s - {candidate.end_time.toFixed(1)}s ({candidate.duration_seconds.toFixed(1)}s)
            </span>
          </div>

          {!isEditing ? (
            <h4 className="text-sm font-semibold text-white leading-snug truncate">
              {candidate.title}
            </h4>
          ) : (
            <form onSubmit={handleSaveEdit} className="space-y-2 pt-1">
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded px-2.5 py-1 text-xs text-white"
                placeholder="Clip title"
                required
              />
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={editStart}
                  onChange={(e) => setEditStart(parseFloat(e.target.value) || 0)}
                  className="w-24 bg-zinc-950 border border-zinc-700 rounded px-2 py-1 text-xs text-white font-mono"
                  placeholder="Start (s)"
                />
                <span className="text-zinc-500 text-xs">to</span>
                <input
                  type="number"
                  step="0.1"
                  min={editStart + 1}
                  value={editEnd}
                  onChange={(e) => setEditEnd(parseFloat(e.target.value) || 0)}
                  className="w-24 bg-zinc-950 border border-zinc-700 rounded px-2 py-1 text-xs text-white font-mono"
                  placeholder="End (s)"
                />
                <button
                  type="submit"
                  className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-2 py-1 bg-zinc-800 text-zinc-300 text-xs rounded"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Score Pill */}
        <button
          onClick={() => setShowBreakdown(!showBreakdown)}
          className={`flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-bold font-mono transition-transform active:scale-95 ${getScoreBadgeColor(
            candidate.overall_score
          )}`}
          title="Click to view score breakdown"
        >
          <Sparkles className="w-3.5 h-3.5 fill-current" />
          {candidate.overall_score}
          {showBreakdown ? <ChevronUp className="w-3 h-3 ml-0.5" /> : <ChevronDown className="w-3 h-3 ml-0.5" />}
        </button>
      </div>

      {/* Hook & Summary */}
      <div className="space-y-1.5 text-xs text-zinc-300">
        {candidate.hook && (
          <div className="flex items-start gap-1.5 bg-zinc-950/60 p-2 rounded-lg border border-zinc-800/80">
            <Quote className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0 mt-0.5" />
            <p className="italic text-zinc-300 font-serif leading-relaxed">
              "{candidate.hook}"
            </p>
          </div>
        )}

        {candidate.summary && (
          <p className="text-zinc-400 text-[11px] leading-relaxed line-clamp-2">
            {candidate.summary}
          </p>
        )}
      </div>

      {/* Collapsible Score Breakdown */}
      {showBreakdown && (
        <HighlightScoreBreakdown
          scoreBreakdown={candidate.score_breakdown}
          overallScore={candidate.overall_score}
        />
      )}

      {/* Action Controls */}
      <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onPreview(candidate.start_time)}
            className="px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors flex items-center gap-1"
            title="Preview section in video player"
          >
            <Play className="w-3 h-3 fill-current ml-0.5" /> Preview
          </button>

          {!isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="p-1.5 hover:bg-zinc-800 text-zinc-400 hover:text-white rounded-lg transition-colors"
              title="Edit start and end boundaries"
            >
              <Edit2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {candidate.status !== 'approved' && (
            <button
              onClick={() => onApprove(candidate.id)}
              className="px-2.5 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 text-xs font-medium rounded-lg border border-emerald-500/30 transition-colors flex items-center gap-1"
              title="Approve candidate"
            >
              <Check className="w-3 h-3" /> Approve
            </button>
          )}

          {candidate.status !== 'rejected' && (
            <button
              onClick={() => onReject(candidate.id)}
              className="px-2 py-1.5 hover:bg-rose-600/20 text-zinc-400 hover:text-rose-400 text-xs font-medium rounded-lg transition-colors"
              title="Reject candidate"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          <button
            onClick={() => onCreateClip(candidate)}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-md shadow-indigo-600/20 transition-all flex items-center gap-1.5"
            title="Render this candidate into a short clip"
          >
            <Scissors className="w-3 h-3" />
            Render Clip
          </button>
        </div>
      </div>
    </div>
  );
};
