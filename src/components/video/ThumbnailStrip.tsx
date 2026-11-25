import React from 'react';
import { Clock } from 'lucide-react';

interface ThumbnailItem {
  index: number;
  timestamp: number;
  file_path: string;
  filename: string;
}

interface ThumbnailStripProps {
  thumbnails: ThumbnailItem[];
  duration: number;
  currentTime?: number;
  onSeek: (timestamp: number) => void;
  className?: string;
}

export const ThumbnailStrip: React.FC<ThumbnailStripProps> = ({
  thumbnails,
  duration,
  currentTime = 0,
  onSeek,
  className = '',
}) => {
  if (!thumbnails || thumbnails.length === 0) {
    return null;
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`bg-zinc-900/80 border border-zinc-800 rounded-xl p-3 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-indigo-400" /> Timeline Frame Previews
        </span>
        <span className="text-xs text-zinc-500 font-mono">
          {thumbnails.length} frames
        </span>
      </div>

      <div className="flex gap-1.5 overflow-x-auto pb-1.5 scrollbar-thin scrollbar-thumb-zinc-700">
        {thumbnails.map((thumb) => {
          const isActive = Math.abs((currentTime || 0) - thumb.timestamp) < (duration / thumbnails.length);
          return (
            <button
              key={thumb.index}
              onClick={() => onSeek(thumb.timestamp)}
              className={`relative flex-shrink-0 group rounded-lg overflow-hidden border-2 transition-all cursor-pointer ${
                isActive ? 'border-indigo-500 ring-2 ring-indigo-500/30' : 'border-zinc-800 hover:border-zinc-600'
              }`}
            >
              <img
                src={`http://127.0.0.1:8000/storage/thumbnails/${thumb.filename}`}
                alt={`Frame at ${thumb.timestamp}s`}
                className="w-24 h-14 object-cover group-hover:scale-105 transition-transform duration-200"
                onError={(e) => {
                  // Fallback placeholder if image not yet cached
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <span className="absolute bottom-1 right-1 bg-black/80 text-[10px] font-mono text-zinc-300 px-1 py-0.5 rounded">
                {formatTime(thumb.timestamp)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
