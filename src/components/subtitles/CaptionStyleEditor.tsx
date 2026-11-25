import React from 'react';
import { Type, Palette, AlignCenter, Sparkles, Layers, Sliders } from 'lucide-react';
import { CaptionPresetData } from '../../services/api';

interface CaptionStyleEditorProps {
  style: CaptionPresetData;
  onChange: (updated: CaptionPresetData) => void;
}

const COMMON_FONTS = [
  'Arial',
  'Arial Black',
  'Montserrat',
  'Impact',
  'Trebuchet MS',
  'Segoe UI',
  'Georgia',
  'Verdana',
  'Tahoma',
];

const ANIMATION_STYLES = [
  { id: 'karaoke_pop', label: 'Karaoke Pop', desc: 'Active word pops with color & scale' },
  { id: 'word_by_word', label: 'Word by Word', desc: 'Reveals text progressively' },
  { id: 'phrase_fade', label: 'Phrase Fade', desc: 'Smooth full sentence transitions' },
  { id: 'static', label: 'Classic Static', desc: 'Clean unanimated subtitles' },
];

export const CaptionStyleEditor: React.FC<CaptionStyleEditorProps> = ({ style, onChange }) => {
  return (
    <div className="space-y-4 text-xs">
      {/* 1. Font Family & Size */}
      <div>
        <label className="flex items-center gap-1.5 text-text-muted font-semibold uppercase tracking-wider mb-2">
          <Type className="w-3.5 h-3.5 text-primary" />
          <span>Typography</span>
        </label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="block text-[10px] text-text-muted mb-1">Font Family</span>
            <select
              value={style.font_family}
              onChange={(e) => onChange({ ...style, font_family: e.target.value })}
              className="w-full bg-surface-muted/60 border border-border-muted rounded-lg p-2 text-text-primary text-xs focus:border-primary focus:outline-none"
            >
              {COMMON_FONTS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex justify-between text-[10px] text-text-muted mb-1">
              <span>Font Size</span>
              <span className="font-mono text-text-primary">{style.font_size}px</span>
            </div>
            <input
              type="range"
              min="36"
              max="96"
              step="2"
              value={style.font_size}
              onChange={(e) => onChange({ ...style, font_size: parseInt(e.target.value) })}
              className="w-full accent-primary mt-2"
            />
          </div>
        </div>

        {/* Bold & Italic Toggles */}
        <div className="flex gap-2 mt-2">
          <button
            type="button"
            onClick={() => onChange({ ...style, bold: !style.bold })}
            className={`flex-1 py-1.5 rounded-lg border text-xs font-bold transition-colors ${
              style.bold
                ? 'border-primary bg-primary/20 text-primary'
                : 'border-border-muted bg-surface-muted/30 text-text-muted'
            }`}
          >
            Bold
          </button>
          <button
            type="button"
            onClick={() => onChange({ ...style, italic: !style.italic })}
            className={`flex-1 py-1.5 rounded-lg border text-xs italic transition-colors ${
              style.italic
                ? 'border-primary bg-primary/20 text-primary'
                : 'border-border-muted bg-surface-muted/30 text-text-muted'
            }`}
          >
            Italic
          </button>
        </div>
      </div>

      {/* 2. Color Palette */}
      <div>
        <label className="flex items-center gap-1.5 text-text-muted font-semibold uppercase tracking-wider mb-2">
          <Palette className="w-3.5 h-3.5 text-primary" />
          <span>Colors & Stroke</span>
        </label>
        <div className="grid grid-cols-3 gap-2">
          {/* Primary Text Color */}
          <div className="p-2 rounded-lg border border-border-muted bg-surface-muted/30">
            <span className="block text-[10px] text-text-muted mb-1">Base Text</span>
            <div className="flex items-center gap-1.5">
              <input
                type="color"
                value={style.primary_color}
                onChange={(e) => onChange({ ...style, primary_color: e.target.value })}
                className="w-6 h-6 rounded cursor-pointer border border-white/20 bg-transparent"
              />
              <span className="font-mono text-[10px] text-text-primary uppercase truncate">
                {style.primary_color}
              </span>
            </div>
          </div>

          {/* Karaoke Highlight Color */}
          <div className="p-2 rounded-lg border border-border-muted bg-surface-muted/30">
            <span className="block text-[10px] text-text-muted mb-1">Karaoke Pop</span>
            <div className="flex items-center gap-1.5">
              <input
                type="color"
                value={style.highlight_color}
                onChange={(e) => onChange({ ...style, highlight_color: e.target.value })}
                className="w-6 h-6 rounded cursor-pointer border border-white/20 bg-transparent"
              />
              <span className="font-mono text-[10px] text-text-primary uppercase truncate">
                {style.highlight_color}
              </span>
            </div>
          </div>

          {/* Outline Color */}
          <div className="p-2 rounded-lg border border-border-muted bg-surface-muted/30">
            <span className="block text-[10px] text-text-muted mb-1">Outline</span>
            <div className="flex items-center gap-1.5">
              <input
                type="color"
                value={style.outline_color}
                onChange={(e) => onChange({ ...style, outline_color: e.target.value })}
                className="w-6 h-6 rounded cursor-pointer border border-white/20 bg-transparent"
              />
              <span className="font-mono text-[10px] text-text-primary uppercase truncate">
                {style.outline_color}
              </span>
            </div>
          </div>
        </div>

        {/* Outline Width & Shadow Width Sliders */}
        <div className="grid grid-cols-2 gap-3 mt-3">
          <div>
            <div className="flex justify-between text-[10px] text-text-muted mb-1">
              <span>Outline Width</span>
              <span className="font-mono text-text-primary">{style.outline_width}px</span>
            </div>
            <input
              type="range"
              min="0"
              max="12"
              value={style.outline_width}
              onChange={(e) => onChange({ ...style, outline_width: parseInt(e.target.value) })}
              className="w-full accent-primary"
            />
          </div>

          <div>
            <div className="flex justify-between text-[10px] text-text-muted mb-1">
              <span>Drop Shadow</span>
              <span className="font-mono text-text-primary">{style.shadow_width}px</span>
            </div>
            <input
              type="range"
              min="0"
              max="8"
              value={style.shadow_width}
              onChange={(e) => onChange({ ...style, shadow_width: parseInt(e.target.value) })}
              className="w-full accent-primary"
            />
          </div>
        </div>
      </div>

      {/* 3. Layout & Mobile Safe Margins */}
      <div>
        <label className="flex items-center gap-1.5 text-text-muted font-semibold uppercase tracking-wider mb-2">
          <AlignCenter className="w-3.5 h-3.5 text-primary" />
          <span>Position & Layout</span>
        </label>

        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-[10px] text-text-muted mb-1">
              <span>Vertical Bottom Margin (Safe Zone)</span>
              <span className="font-mono text-text-primary">{style.margin_v}px</span>
            </div>
            <input
              type="range"
              min="80"
              max="450"
              step="10"
              value={style.margin_v}
              onChange={(e) => onChange({ ...style, margin_v: parseInt(e.target.value) })}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-[9px] text-text-muted mt-0.5">
              <span>Lower (Standard)</span>
              <span>Upper (Above TikTok UI)</span>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-[10px] text-text-muted mb-1">
              <span>Max Words Per Line</span>
              <span className="font-mono text-text-primary">{style.max_words_per_line}</span>
            </div>
            <div className="flex gap-2">
              {[2, 3, 4, 5, 6].map((num) => (
                <button
                  key={num}
                  type="button"
                  onClick={() => onChange({ ...style, max_words_per_line: num })}
                  className={`flex-1 py-1 rounded-lg border text-xs font-semibold ${
                    style.max_words_per_line === num
                      ? 'border-primary bg-primary text-black'
                      : 'border-border-muted bg-surface-muted/30 text-text-muted hover:border-border-base'
                  }`}
                >
                  {num}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Animation Style */}
      <div>
        <label className="flex items-center gap-1.5 text-text-muted font-semibold uppercase tracking-wider mb-2">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span>Animation Effect</span>
        </label>
        <div className="grid grid-cols-2 gap-2">
          {ANIMATION_STYLES.map((anim) => {
            const isSelected = style.animation_style === anim.id;
            return (
              <button
                key={anim.id}
                type="button"
                onClick={() => onChange({ ...style, animation_style: anim.id })}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  isSelected
                    ? 'border-primary bg-primary/10 text-text-primary font-medium'
                    : 'border-border-muted bg-surface-muted/40 text-text-muted hover:border-border-base'
                }`}
              >
                <div className="font-semibold text-xs mb-0.5">{anim.label}</div>
                <div className="text-[10px] text-text-muted">{anim.desc}</div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
