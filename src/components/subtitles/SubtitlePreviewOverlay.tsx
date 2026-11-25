import React from 'react';
import { CaptionPresetData, SubtitleSegmentData } from '../../services/api';

interface SubtitlePreviewOverlayProps {
  segments: SubtitleSegmentData[];
  preset?: CaptionPresetData;
  currentTime: number;
  isEnabled?: boolean;
}

export const SubtitlePreviewOverlay: React.FC<SubtitlePreviewOverlayProps> = ({
  segments,
  preset,
  currentTime,
  isEnabled = true,
}) => {
  if (!isEnabled || !preset || !segments || segments.length === 0) {
    return null;
  }

  // Find active segment for currentTime
  const activeSegment = segments.find(
    (s) => currentTime >= s.start && currentTime <= s.end
  );

  if (!activeSegment) {
    return null;
  }

  // Chunk words based on preset.max_words_per_line
  const words = activeSegment.words || [];
  const chunkSize = Math.max(1, preset.max_words_per_line || 4);
  const wordChunks = [];
  for (let i = 0; i < words.length; i += chunkSize) {
    wordChunks.push(words.slice(i, i + chunkSize));
  }

  // Find current active chunk
  const activeChunk =
    wordChunks.find((chunk) => {
      const cStart = chunk[0].start;
      const cEnd = chunk[chunk.length - 1].end;
      return currentTime >= cStart && currentTime <= cEnd;
    }) || wordChunks[0];

  // Calculate vertical bottom position percent (relative to 1920 canvas)
  const bottomPct = Math.min(45, Math.max(5, (preset.margin_v / 1920) * 100));

  return (
    <div
      className="absolute inset-x-0 pointer-events-none flex justify-center z-20 px-4"
      style={{
        bottom: `${bottomPct}%`,
      }}
    >
      <div
        className="text-center tracking-wide uppercase transition-all duration-75 select-none"
        style={{
          fontFamily: preset.font_family,
          fontSize: `${Math.max(18, Math.min(36, preset.font_size / 2.2))}px`,
          fontWeight: preset.bold ? 'bold' : 'normal',
          fontStyle: preset.italic ? 'italic' : 'normal',
          WebkitTextStroke: `${Math.min(4, preset.outline_width / 2.5)}px ${preset.outline_color}`,
          filter: `drop-shadow(0 ${preset.shadow_width}px ${preset.shadow_width * 2}px black)`,
        }}
      >
        {activeChunk && activeChunk.length > 0 ? (
          <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
            {activeChunk.map((w, idx) => {
              const isWordActive =
                preset.animation_style !== 'static' &&
                currentTime >= w.start &&
                currentTime <= w.end;

              return (
                <span
                  key={`${w.word}-${idx}`}
                  className={`inline-block transition-transform duration-100 ${
                    isWordActive ? 'scale-110 font-extrabold' : ''
                  }`}
                  style={{
                    color: isWordActive ? preset.highlight_color : preset.primary_color,
                  }}
                >
                  {w.word}
                </span>
              );
            })}
          </div>
        ) : (
          <span style={{ color: preset.primary_color }}>{activeSegment.text}</span>
        )}
      </div>
    </div>
  );
};
