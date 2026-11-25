import React, { useState, useEffect } from 'react';
import { 
  Sparkles, Cpu, Clock, Layers, Loader2, Download, 
  Check, AlertCircle 
} from 'lucide-react';
import { Modal } from '../ui/Modal';
import { api, LLMModelData } from '../../services/api';

interface HighlightSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartAnalysis: (params: {
    model_name: string;
    content_type: string;
    target_duration_min: number;
    target_duration_max: number;
    max_candidates: number;
    auto_create_clips?: boolean;
  }) => Promise<void>;
}

export const HighlightSettingsModal: React.FC<HighlightSettingsModalProps> = ({
  isOpen,
  onClose,
  onStartAnalysis,
}) => {
  const [models, setModels] = useState<LLMModelData[]>([]);
  const [selectedModel, setSelectedModel] = useState('qwen-2.5-3b');
  const [contentType, setContentType] = useState('general');
  const [durationPreset, setDurationPreset] = useState('30-60');
  const [customMin, setCustomMin] = useState(30);
  const [customMax, setCustomMax] = useState(60);
  const [maxCandidates, setMaxCandidates] = useState(5);
  const [autoCreateClips, setAutoCreateClips] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadModels();
    }
  }, [isOpen]);

  const loadModels = async () => {
    setLoadingModels(true);
    try {
      const data = await api.listLlmModels();
      setModels(data);
      const defaultMod = data.find((m) => m.is_default);
      if (defaultMod) {
        setSelectedModel(defaultMod.id);
      }
    } catch (e) {
      console.warn('Failed to load LLM models:', e);
    } finally {
      setLoadingModels(false);
    }
  };

  const handleDownload = async (modelId: string) => {
    try {
      await api.downloadLlmModel(modelId);
      await loadModels();
    } catch (e) {
      console.error(e);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    let minDur = 30;
    let maxDur = 60;
    if (durationPreset === '15-30') {
      minDur = 15;
      maxDur = 30;
    } else if (durationPreset === '30-45') {
      minDur = 30;
      maxDur = 45;
    } else if (durationPreset === '30-60') {
      minDur = 30;
      maxDur = 60;
    } else if (durationPreset === '60-90') {
      minDur = 60;
      maxDur = 90;
    } else if (durationPreset === 'custom') {
      minDur = customMin;
      maxDur = customMax;
    }

    try {
      await onStartAnalysis({
        model_name: selectedModel,
        content_type: contentType,
        target_duration_min: minDur,
        target_duration_max: maxDur,
        max_candidates: maxCandidates,
        auto_create_clips: autoCreateClips,
      });
      onClose();
    } catch (err) {
      console.error('Failed to trigger highlight analysis:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectedModelData = models.find((m) => m.id === selectedModel);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="AI Highlight Discovery Settings">
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        {/* Model Selection */}
        <div>
          <label className="block text-zinc-300 font-semibold mb-1 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            Local LLM Model
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {models.map((m) => (
              <div
                key={m.id}
                onClick={() => setSelectedModel(m.id)}
                className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
                  selectedModel === m.id
                    ? 'bg-indigo-600/15 border-indigo-500 text-white'
                    : 'bg-zinc-950/70 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-white truncate">{m.name}</span>
                  {m.is_installed ? (
                    <span className="text-[10px] text-emerald-400 flex items-center gap-0.5">
                      <Check className="w-2.5 h-2.5" /> Installed
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownload(m.id);
                      }}
                      className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5"
                    >
                      <Download className="w-2.5 h-2.5" /> Download
                    </button>
                  )}
                </div>
                <p className="text-[11px] text-zinc-500 mt-0.5 leading-snug line-clamp-2">
                  {m.description}
                </p>
                <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 mt-1.5 pt-1 border-t border-zinc-800/60">
                  <span>{(m.file_size_bytes / (1024 * 1024 * 1024)).toFixed(2)} GB</span>
                  <span>{m.parameter_count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Content Type Selector */}
        <div>
          <label className="block text-zinc-300 font-semibold mb-1 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            Content Type Focus
          </label>
          <select
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
          >
            <option value="general">General / Mixed Content (Balanced)</option>
            <option value="podcast">Podcast (Conversations & Hot Takes)</option>
            <option value="interview">Interview (Revelations & Insights)</option>
            <option value="educational">Educational (Explanations & Facts)</option>
            <option value="tutorial">Tutorial (How-To & Actionable Hacks)</option>
            <option value="motivational">Motivational (Inspirational & Stories)</option>
            <option value="business">Business (Tactics & Market Insights)</option>
            <option value="gaming">Gaming (Clutch Plays & Funny Moments)</option>
          </select>
        </div>

        {/* Target Clip Duration */}
        <div>
          <label className="block text-zinc-300 font-semibold mb-1 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            Target Clip Duration
          </label>
          <div className="grid grid-cols-4 gap-2 mb-2">
            {[
              { id: '15-30', label: '15–30s (Micro)' },
              { id: '30-45', label: '30–45s (Reels)' },
              { id: '30-60', label: '30–60s (Default)' },
              { id: '60-90', label: '60–90s (Longer)' },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setDurationPreset(p.id)}
                className={`py-1.5 px-2 rounded-lg text-[11px] font-medium border text-center transition-colors ${
                  durationPreset === p.id
                    ? 'bg-indigo-600 text-white border-indigo-500'
                    : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {durationPreset === 'custom' && (
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div>
                <label className="block text-[11px] text-zinc-400 mb-0.5">Min Duration (s)</label>
                <input
                  type="number"
                  min="10"
                  max="120"
                  value={customMin}
                  onChange={(e) => setCustomMin(parseInt(e.target.value) || 15)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-white font-mono text-xs"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-0.5">Max Duration (s)</label>
                <input
                  type="number"
                  min={customMin + 5}
                  max="180"
                  value={customMax}
                  onChange={(e) => setCustomMax(parseInt(e.target.value) || 60)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1 text-white font-mono text-xs"
                />
              </div>
            </div>
          )}
        </div>

        {/* Max Candidates */}
        <div>
          <label className="block text-zinc-300 font-semibold mb-1">
            Max Candidates to Discover: <span className="text-indigo-400 font-mono">{maxCandidates}</span>
          </label>
          <input
            type="range"
            min="3"
            max="12"
            step="1"
            value={maxCandidates}
            onChange={(e) => setMaxCandidates(parseInt(e.target.value) || 5)}
            className="w-full accent-indigo-600 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-zinc-500 font-mono mt-1">
            <span>3 clips</span>
            <span>6 clips</span>
            <span>12 clips</span>
          </div>
        </div>

        {/* Auto Create Clips Toggle */}
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={autoCreateClips}
              onChange={(e) => setAutoCreateClips(e.target.checked)}
              className="rounded bg-zinc-900 border-zinc-700 text-indigo-600 focus:ring-indigo-500 w-4 h-4"
            />
            <div className="flex-1">
              <span className="text-xs font-semibold text-white">Auto-generate short clips from highlights</span>
              <p className="text-[11px] text-zinc-400">
                Automatically convert discovered highlights into ready-to-view clips in the project studio.
              </p>
            </div>
          </label>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors text-xs"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-1.5 text-xs disabled:opacity-50"
          >
            {isSubmitting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 fill-current" />
            )}
            Start AI Discovery
          </button>
        </div>
      </form>
    </Modal>
  );
};
