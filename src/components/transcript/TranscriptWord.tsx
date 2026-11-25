import React from 'react';
import { TranscriptWord } from '../../services/api';

interface TranscriptWordProps {
  word: TranscriptWord;
  isActive: boolean;
  onSeek: (time: number) => void;
}

export const TranscriptWordComponent: React.FC<TranscriptWordProps> = ({
  word,
  isActive,
  onSeek,
}) => {
  return (
    <span
      onClick={(e) => {
        e.stopPropagation();
        onSeek(word.start);
      }}
      title={`[${word.start.toFixed(2)}s - ${word.end.toFixed(2)}s] (Prob: ${(word.prob * 100).toFixed(0)}%)`}
      className={`inline-block px-1 py-0.5 rounded transition-all cursor-pointer select-text ${
        isActive
          ? 'bg-indigo-600 text-white font-semibold ring-2 ring-indigo-400/40 shadow-sm'
          : 'text-zinc-200 hover:bg-zinc-800 hover:text-white'
      }`}
    >
      {word.word}
    </span>
  );
};
