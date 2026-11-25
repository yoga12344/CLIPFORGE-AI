import React, { useState } from 'react';
import {
  FileText,
  Search,
  Scissors,
  Layers,
  Clock,
  Play,
  Check,
  Edit2,
  X,
  AlertCircle,
  Plus,
} from 'lucide-react';
import { SubtitleSegmentData, SubtitleWordData } from '../../services/api';

interface SubtitleEditorProps {
  segments: SubtitleSegmentData[];
  currentTime: number;
  onSeek: (seconds: number) => void;
  onUpdateSegment: (segmentId: string, updated: Partial<SubtitleSegmentData>) => Promise<void>;
  onSplitSegment: (segmentId: string, wordIndex: number) => Promise<void>;
  onMergeSegments: (segId1: string, segId2: string) => Promise<void>;
}

export const SubtitleEditor: React.FC<SubtitleEditorProps> = ({
  segments,
  currentTime,
  onSeek,
  onUpdateSegment,
  onSplitSegment,
  onMergeSegments,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingWord, setEditingWord] = useState<{
    segmentId: string;
    wordIndex: number;
    word: SubtitleWordData;
  } | null>(null);

  const [editWordText, setEditWordText] = useState('');
  const [editWordStart, setEditWordStart] = useState(0);
  const [editWordEnd, setEditWordEnd] = useState(0);

  // Filter segments by search query
  const filteredSegments = segments.filter((s) =>
    s.text.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleStartEditWord = (segmentId: string, wordIndex: number, w: SubtitleWordData) => {
    setEditingWord({ segmentId, wordIndex, word: w });
    setEditWordText(w.word);
    setEditWordStart(w.start);
    setEditWordEnd(w.end);
  };

  const handleSaveEditWord = async () => {
    if (!editingWord) return;
    const { segmentId, wordIndex } = editingWord;
    const seg = segments.find((s) => s.id === segmentId);
    if (!seg) return;

    const newWords = [...seg.words];
    newWords[wordIndex] = {
      ...newWords[wordIndex],
      word: editWordText.trim(),
      start: editWordStart,
      end: editWordEnd,
      edited: true,
    };

    await onUpdateSegment(segmentId, {
      words: newWords,
      text: newWords.map((w) => w.word).join(' '),
      start: newWords[0].start,
      end: newWords[newWords.length - 1].end,
    });

    setEditingWord(null);
  };

  return (
    <div className="flex flex-col h-full space-y-3">
      {/* Search Header */}
      <div className="relative">
        <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-text-muted" />
        <input
          type="text"
          placeholder="Search subtitle transcript..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-surface-muted/60 border border-border-muted rounded-xl pl-9 pr-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-primary focus:outline-none"
        />
      </div>

      {/* Segments List */}
      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {filteredSegments.length === 0 ? (
          <div className="p-8 text-center text-text-muted text-xs">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <span>No subtitle segments found matching search.</span>
          </div>
        ) : (
          filteredSegments.map((seg, idx) => {
            const isCurrentlyActive = currentTime >= seg.start && currentTime <= seg.end;

            return (
              <div
                key={seg.id}
                className={`p-3 rounded-xl border transition-all text-xs ${
                  isCurrentlyActive
                    ? 'border-primary/60 bg-primary/5 shadow-sm ring-1 ring-primary/20'
                    : 'border-border-muted bg-surface-muted/30 hover:border-border-base'
                }`}
              >
                {/* Segment Header */}
                <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-white/5">
                  <button
                    onClick={() => onSeek(seg.start)}
                    className="flex items-center gap-1.5 text-text-muted hover:text-primary transition-colors font-mono text-[11px]"
                  >
                    <Clock className="w-3 h-3 text-primary" />
                    <span>
                      {seg.start.toFixed(2)}s - {seg.end.toFixed(2)}s
                    </span>
                    <span className="text-[10px] text-text-muted">
                      ({(seg.end - seg.start).toFixed(1)}s)
                    </span>
                  </button>

                  <div className="flex items-center gap-1.5">
                    {/* Merge with next segment button */}
                    {idx < filteredSegments.length - 1 && (
                      <button
                        onClick={() => onMergeSegments(seg.id, filteredSegments[idx + 1].id)}
                        title="Merge with next phrase"
                        className="p-1 rounded hover:bg-surface-muted text-text-muted hover:text-text-primary"
                      >
                        <Layers className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Word Chips */}
                <div className="flex flex-wrap gap-1.5">
                  {seg.words.map((w, wIdx) => {
                    const isWordActive = currentTime >= w.start && currentTime <= w.end;
                    const isBeingEdited =
                      editingWord?.segmentId === seg.id && editingWord?.wordIndex === wIdx;

                    return (
                      <div key={`${seg.id}-w-${wIdx}`} className="relative group">
                        <button
                          onClick={() => handleStartEditWord(seg.id, wIdx, w)}
                          className={`px-2 py-0.5 rounded text-xs transition-all ${
                            isWordActive
                              ? 'bg-primary text-black font-bold shadow-sm scale-105'
                              : isBeingEdited
                              ? 'bg-primary/20 border border-primary text-primary'
                              : 'bg-surface-base border border-border-muted text-text-secondary hover:border-primary/50'
                          }`}
                        >
                          {w.word}
                        </button>

                        {/* Split action button on hover */}
                        {wIdx > 0 && (
                          <button
                            onClick={() => onSplitSegment(seg.id, wIdx)}
                            title="Split segment before this word"
                            className="hidden group-hover:flex absolute -left-2 -top-1 w-3.5 h-3.5 bg-zinc-800 text-zinc-300 hover:text-primary border border-border-muted rounded-full items-center justify-center text-[9px] shadow"
                          >
                            <Scissors className="w-2 h-2" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Inline Word Timing Modal / Card */}
      {editingWord && (
        <div className="p-3 bg-surface-base border border-primary/50 rounded-xl shadow-xl space-y-2 text-xs">
          <div className="flex items-center justify-between text-text-muted font-semibold text-[11px]">
            <span>Edit Word & Timing</span>
            <button onClick={() => setEditingWord(null)} className="text-text-muted hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <span className="block text-[10px] text-text-muted mb-0.5">Word</span>
              <input
                type="text"
                value={editWordText}
                onChange={(e) => setEditWordText(e.target.value)}
                className="w-full bg-surface-muted border border-border-muted rounded p-1.5 text-xs text-text-primary focus:border-primary focus:outline-none font-bold"
              />
            </div>
            <div>
              <span className="block text-[10px] text-text-muted mb-0.5">Start (s)</span>
              <input
                type="number"
                step="0.05"
                value={editWordStart}
                onChange={(e) => setEditWordStart(parseFloat(e.target.value) || 0)}
                className="w-full bg-surface-muted border border-border-muted rounded p-1.5 text-xs font-mono text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <span className="block text-[10px] text-text-muted mb-0.5">End (s)</span>
              <input
                type="number"
                step="0.05"
                value={editWordEnd}
                onChange={(e) => setEditWordEnd(parseFloat(e.target.value) || 0)}
                className="w-full bg-surface-muted border border-border-muted rounded p-1.5 text-xs font-mono text-text-primary focus:border-primary focus:outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={() => setEditingWord(null)}
              className="px-2.5 py-1 text-text-muted hover:text-white text-xs"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEditWord}
              className="px-3 py-1 bg-primary text-black font-semibold rounded hover:bg-primary/90 text-xs flex items-center gap-1"
            >
              <Check className="w-3 h-3" /> Save Timing
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
