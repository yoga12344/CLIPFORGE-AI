import React, { useState, useMemo } from 'react';
import { 
  Sparkles, Filter, ArrowUpDown, CheckCircle2, 
  XCircle, Clock, Film, Scissors, Loader2 
} from 'lucide-react';
import { HighlightCandidateData } from '../../services/api';
import { HighlightCandidateCard } from './HighlightCandidateCard';

interface HighlightCandidateListProps {
  candidates: HighlightCandidateData[];
  isLoading: boolean;
  onPreview: (startTime: number) => void;
  onApprove: (candidateId: string) => void;
  onReject: (candidateId: string) => void;
  onEdit: (candidateId: string, startTime: number, endTime: number, title: string) => void;
  onCreateClip: (candidate: HighlightCandidateData) => void;
  onOpenDiscoveryModal: () => void;
}

export const HighlightCandidateList: React.FC<HighlightCandidateListProps> = ({
  candidates,
  isLoading,
  onPreview,
  onApprove,
  onReject,
  onEdit,
  onCreateClip,
  onOpenDiscoveryModal,
}) => {
  const [statusFilter, setStatusFilter] = useState<'all' | 'approved' | 'discovered' | 'rejected'>('all');
  const [sortBy, setSortBy] = useState<'score' | 'time' | 'duration'>('score');

  const filteredAndSortedCandidates = useMemo(() => {
    let list = [...candidates];

    if (statusFilter !== 'all') {
      list = list.filter((c) => {
        if (statusFilter === 'approved') return c.status === 'approved' || c.status === 'ready_for_render';
        return c.status === statusFilter;
      });
    }

    list.sort((a, b) => {
      if (sortBy === 'time') return a.start_time - b.start_time;
      if (sortBy === 'duration') return b.duration_seconds - a.duration_seconds;
      return b.overall_score - a.overall_score;
    });

    return list;
  }, [candidates, statusFilter, sortBy]);

  const approvedCount = candidates.filter((c) => c.status === 'approved' || c.status === 'ready_for_render').length;
  const rejectedCount = candidates.filter((c) => c.status === 'rejected').length;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 space-y-3 text-zinc-500">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
        <p className="text-xs">Loading highlight candidates...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Filter and Controls Bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap border-b border-zinc-800 pb-3">
        {/* Status Filters */}
        <div className="flex items-center gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800 text-xs">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              statusFilter === 'all'
                ? 'bg-zinc-800 text-white'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            All ({candidates.length})
          </button>
          <button
            onClick={() => setStatusFilter('approved')}
            className={`px-2.5 py-1 rounded font-medium transition-colors flex items-center gap-1 ${
              statusFilter === 'approved'
                ? 'bg-emerald-600/30 text-emerald-400 border border-emerald-500/30'
                : 'text-zinc-400 hover:text-emerald-400'
            }`}
          >
            <CheckCircle2 className="w-3 h-3" />
            Approved ({approvedCount})
          </button>
          <button
            onClick={() => setStatusFilter('discovered')}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              statusFilter === 'discovered'
                ? 'bg-zinc-800 text-white'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Discovered
          </button>
          <button
            onClick={() => setStatusFilter('rejected')}
            className={`px-2.5 py-1 rounded font-medium transition-colors flex items-center gap-1 ${
              statusFilter === 'rejected'
                ? 'bg-rose-600/20 text-rose-400 border border-rose-500/30'
                : 'text-zinc-400 hover:text-rose-400'
            }`}
          >
            <XCircle className="w-3 h-3" />
            Rejected ({rejectedCount})
          </button>
        </div>

        {/* Sort Controls */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-zinc-500 flex items-center gap-1">
            <ArrowUpDown className="w-3 h-3" /> Sort:
          </span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1 text-zinc-300 focus:outline-none focus:border-indigo-500 text-xs font-medium"
          >
            <option value="score">Highest Score</option>
            <option value="time">Timeline (Start Time)</option>
            <option value="duration">Longest Duration</option>
          </select>
        </div>
      </div>

      {/* Candidate Cards List */}
      {filteredAndSortedCandidates.length === 0 ? (
        <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-8 text-center space-y-3">
          <Sparkles className="w-10 h-10 text-zinc-600 mx-auto" />
          <h4 className="text-sm font-semibold text-white">No Highlights Found</h4>
          <p className="text-xs text-zinc-400 max-w-sm mx-auto">
            {candidates.length === 0
              ? 'No highlight candidates have been discovered for this video yet. Run AI clip analysis to discover the best moments.'
              : 'No candidates match the selected filter criteria.'}
          </p>
          {candidates.length === 0 && (
            <button
              onClick={onOpenDiscoveryModal}
              className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-indigo-600/20 transition-all inline-flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 fill-current" />
              Discover AI Highlights Now
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAndSortedCandidates.map((candidate) => (
            <HighlightCandidateCard
              key={candidate.id}
              candidate={candidate}
              onPreview={onPreview}
              onApprove={onApprove}
              onReject={onReject}
              onEdit={onEdit}
              onCreateClip={onCreateClip}
            />
          ))}
        </div>
      )}
    </div>
  );
};
