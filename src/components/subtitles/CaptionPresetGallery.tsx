import React from 'react';
import { Check, Sparkles, Sliders } from 'lucide-react';
import { CaptionPresetData } from '../../services/api';

interface CaptionPresetGalleryProps {
  presets: CaptionPresetData[];
  selectedPresetId?: string;
  onSelectPreset: (preset: CaptionPresetData) => void;
  onCustomizePreset?: (preset: CaptionPresetData) => void;
}

export const CaptionPresetGallery: React.FC<CaptionPresetGalleryProps> = ({
  presets,
  selectedPresetId,
  onSelectPreset,
  onCustomizePreset,
}) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs font-semibold text-text-muted uppercase tracking-wider">
        <span>Subtitle Presets</span>
        <span className="text-[10px] text-primary">{presets.length} Styles</span>
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        {presets.map((p) => {
          const isSelected = p.id === selectedPresetId;
          return (
            <div
              key={p.id || p.name}
              onClick={() => onSelectPreset(p)}
              className={`relative group cursor-pointer p-3 rounded-xl border text-left transition-all ${
                isSelected
                  ? 'border-primary bg-primary/10 shadow-[0_0_15px_rgba(250,204,21,0.15)] ring-1 ring-primary/40'
                  : 'border-border-muted bg-surface-muted/40 hover:border-border-base hover:bg-surface-muted/70'
              }`}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-xs text-text-primary truncate">{p.name}</span>
                {isSelected && (
                  <span className="p-0.5 rounded-full bg-primary text-black">
                    <Check className="w-3 h-3 stroke-[3]" />
                  </span>
                )}
              </div>

              {/* Visual Card Style Sample */}
              <div
                className="h-14 rounded-lg bg-black/80 flex items-center justify-center p-2 overflow-hidden border border-white/5 shadow-inner"
              >
                <div
                  style={{
                    fontFamily: p.font_family,
                    fontSize: '13px',
                    fontWeight: p.bold ? 'bold' : 'normal',
                    fontStyle: p.italic ? 'italic' : 'normal',
                    textShadow: `0 0 ${p.shadow_width}px black`,
                    WebkitTextStroke: `${Math.min(2, p.outline_width / 3)}px ${p.outline_color}`,
                  }}
                  className="tracking-wide text-center uppercase"
                >
                  <span style={{ color: p.primary_color }}>THIS IS </span>
                  <span style={{ color: p.highlight_color }} className="font-extrabold scale-110 inline-block">
                    VIRAL
                  </span>
                </div>
              </div>

              {/* Style badges */}
              <div className="flex items-center justify-between mt-2 pt-1 border-t border-white/5 text-[10px] text-text-muted">
                <span className="truncate">{p.font_family}</span>
                <span className="font-mono text-text-secondary">{p.font_size}pt</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
