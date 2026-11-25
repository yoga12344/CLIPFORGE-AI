import React from 'react';
import { Search, X, ChevronUp, ChevronDown } from 'lucide-react';

interface TranscriptSearchProps {
  query: string;
  onQueryChange: (q: string) => void;
  matchCount: number;
  currentMatchIndex: number;
  onNextMatch: () => void;
  onPrevMatch: () => void;
  className?: string;
}

export const TranscriptSearch: React.FC<TranscriptSearchProps> = ({
  query,
  onQueryChange,
  matchCount,
  currentMatchIndex,
  onNextMatch,
  onPrevMatch,
  className = '',
}) => {
  return (
    <div className={`relative flex items-center bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 focus-within:border-indigo-500 transition-colors ${className}`}>
      <Search className="w-3.5 h-3.5 text-zinc-400 mr-2 flex-shrink-0" />
      <input
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Search transcript..."
        className="w-full bg-transparent text-xs text-white placeholder-zinc-500 focus:outline-none"
      />

      {query && (
        <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
          <span className="text-[10px] font-mono text-zinc-400">
            {matchCount > 0 ? `${currentMatchIndex + 1}/${matchCount}` : '0 found'}
          </span>

          {matchCount > 0 && (
            <div className="flex items-center gap-0.5 border-l border-zinc-800 pl-1.5">
              <button
                type="button"
                onClick={onPrevMatch}
                className="p-0.5 text-zinc-400 hover:text-white rounded transition-colors"
                title="Previous match"
              >
                <ChevronUp className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={onNextMatch}
                className="p-0.5 text-zinc-400 hover:text-white rounded transition-colors"
                title="Next match"
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={() => onQueryChange('')}
            className="p-0.5 text-zinc-400 hover:text-white rounded transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
};
