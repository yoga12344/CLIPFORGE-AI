import React, { useState, useEffect } from 'react';
import { Palette, Plus, Check, Trash2, Sliders, Type, Sparkles, Eye, RefreshCw } from 'lucide-react';
import { api, CaptionPresetData } from '../services/api';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

export const SubtitleTemplatesPage: React.FC = () => {
  const [presets, setPresets] = useState<CaptionPresetData[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<CaptionPresetData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [previewText, setPreviewText] = useState('Transform long videos into viral shorts in 1 click');
  const [activeWordIdx, setActiveWordIdx] = useState(3);

  const loadPresets = async () => {
    setIsLoading(true);
    try {
      const data = await api.getCaptionPresets();
      setPresets(data);
      if (data.length > 0 && !selectedPreset) {
        setSelectedPreset(data[0]);
      }
    } catch (err) {
      console.warn('Could not load presets:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPresets();
  }, []);

  // Animate word pop preview
  useEffect(() => {
    const words = previewText.split(' ');
    const timer = setInterval(() => {
      setActiveWordIdx((prev) => (prev + 1) % words.length);
    }, 600);
    return () => clearInterval(timer);
  }, [previewText]);

  const words = previewText.split(' ');

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0e0e13] text-zinc-100 overflow-hidden">
      {/* Header */}
      <div className="h-14 border-b border-[#1f1f2b] px-6 flex items-center justify-between bg-[#121218]/80 backdrop-blur flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Palette className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-zinc-100">Brand Templates & Caption Styles</h1>
            <p className="text-[11px] text-zinc-400">Customizable SubStation Alpha (.ass) typography and karaoke animations</p>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={loadPresets} icon={RefreshCw}>
          Refresh Presets
        </Button>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Preset Cards List */}
        <div className="w-80 border-r border-[#1f1f2b] bg-[#101017] p-4 overflow-y-auto space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold text-zinc-400 px-1">
            <span>Broadcast Presets ({presets.length})</span>
          </div>

          {isLoading ? (
            <div className="p-6 text-center text-xs text-zinc-500">Loading templates...</div>
          ) : (
            presets.map((preset) => {
              const isSelected = selectedPreset?.id === preset.id;
              return (
                <div
                  key={preset.id}
                  onClick={() => setSelectedPreset(preset)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-purple-600/15 border-purple-500/50 shadow-lg shadow-purple-600/10'
                      : 'bg-[#151520] border-[#20202e] hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-zinc-200">{preset.name}</span>
                    {preset.is_default && (
                      <span className="text-[9px] font-semibold bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30">
                        Default
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-zinc-400">
                    <span className="font-mono">{preset.font_family}</span>
                    <span>•</span>
                    <span>{preset.font_size}pt</span>
                    <span>•</span>
                    <span
                      className="w-3 h-3 rounded-full border border-black/40 inline-block"
                      style={{ backgroundColor: preset.highlight_color }}
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Live Typography Preview Canvas */}
        <div className="flex-1 flex flex-col p-6 items-center justify-center bg-[#09090d] relative overflow-hidden">
          {selectedPreset ? (
            <div className="flex flex-col items-center max-w-2xl w-full">
              {/* 9:16 Preview Box */}
              <div className="w-[320px] h-[520px] bg-slate-950 rounded-2xl border border-white/10 shadow-2xl relative flex flex-col justify-end p-6 overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent pointer-events-none" />
                
                {/* Simulated Video Placeholder */}
                <div className="absolute top-12 inset-x-6 h-48 rounded-xl bg-purple-900/20 border border-purple-500/20 flex flex-col items-center justify-center text-center p-3">
                  <Sparkles className="w-6 h-6 text-purple-400 mb-1" />
                  <span className="text-xs font-medium text-purple-300">Face Tracking Active</span>
                  <span className="text-[10px] text-zinc-500 font-mono">Collision Clearance: 280px</span>
                </div>

                {/* Live Caption Text Render */}
                <div
                  className="relative z-10 text-center leading-snug drop-shadow-md"
                  style={{
                    fontFamily: selectedPreset.font_family,
                    fontSize: `${Math.min(28, selectedPreset.font_size / 2.2)}px`,
                    fontWeight: selectedPreset.bold ? 800 : 400,
                    fontStyle: selectedPreset.italic ? 'italic' : 'normal',
                  }}
                >
                  {words.map((w, idx) => {
                    const isActive = idx === activeWordIdx;
                    return (
                      <span
                        key={idx}
                        className={`inline-block mx-0.5 transition-all duration-150 ${
                          isActive ? 'scale-110' : 'scale-100'
                        }`}
                        style={{
                          color: isActive ? selectedPreset.highlight_color : selectedPreset.primary_color,
                          WebkitTextStroke: `${Math.max(1, selectedPreset.outline_width / 2)}px ${selectedPreset.outline_color}`,
                        }}
                      >
                        {w}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Preset Properties Bar */}
              <div className="mt-6 w-full bg-[#13131c] p-4 rounded-xl border border-[#212130] grid grid-cols-4 gap-4 text-xs">
                <div>
                  <span className="text-zinc-500 block text-[10px]">Font Family</span>
                  <span className="font-bold text-zinc-200">{selectedPreset.font_family}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">Font Size</span>
                  <span className="font-bold text-zinc-200">{selectedPreset.font_size} pt</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">Animation Style</span>
                  <span className="font-bold text-zinc-200">{selectedPreset.animation_style}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">Max Words / Line</span>
                  <span className="font-bold text-zinc-200">{selectedPreset.max_words_per_line}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-zinc-500 text-sm">Select a caption preset to view live typography</div>
          )}
        </div>
      </div>
    </div>
  );
};
