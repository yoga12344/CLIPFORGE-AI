import React, { useState, useEffect } from 'react';
import { Sparkles, Cpu, Globe, Sliders, Loader2, HardDrive, CheckCircle2 } from 'lucide-react';
import { api, WhisperModelData, InferenceStatusData } from '../../services/api';
import { Modal } from '../ui/Modal';
import { ModelSelector } from './ModelSelector';
import { LanguageSelector } from './LanguageSelector';

interface TranscriptionSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartTranscription: (config: {
    model_name: string;
    language?: string;
    device: string;
    vad_filter: boolean;
    vad_threshold: number;
    word_timestamps: boolean;
  }) => Promise<void>;
  initialModel?: string;
  isRetranscribe?: boolean;
}

export const TranscriptionSettingsModal: React.FC<TranscriptionSettingsModalProps> = ({
  isOpen,
  onClose,
  onStartTranscription,
  initialModel = 'small',
  isRetranscribe = false,
}) => {
  const [models, setModels] = useState<WhisperModelData[]>([]);
  const [inferenceStatus, setInferenceStatus] = useState<InferenceStatusData | null>(null);
  const [selectedModel, setSelectedModel] = useState(initialModel);
  const [selectedLanguage, setSelectedLanguage] = useState('');
  const [selectedDevice, setSelectedDevice] = useState('auto');
  const [vadFilter, setVadFilter] = useState(true);
  const [wordTimestamps, setWordTimestamps] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const loadData = async () => {
      setIsLoading(true);
      try {
        const [modelsList, inf] = await Promise.all([
          api.listAiModels(),
          api.getInferenceStatus(),
        ]);
        setModels(modelsList);
        setInferenceStatus(inf);
      } catch (e) {
        console.warn('Failed to load models list:', e);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onStartTranscription({
        model_name: selectedModel,
        language: selectedLanguage ? selectedLanguage : undefined,
        device: selectedDevice,
        vad_filter: vadFilter,
        vad_threshold: 0.5,
        word_timestamps: wordTimestamps,
      });
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectedModelData = models.find((m) => m.model_id === selectedModel);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isRetranscribe ? 'Retranscribe Audio' : 'Start AI Speech Transcription'}
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        {isLoading ? (
          <div className="py-8 flex items-center justify-center text-zinc-500">
            <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading local AI models...
          </div>
        ) : (
          <>
            {/* Model Selection */}
            <div>
              <label className="block text-zinc-300 font-medium mb-1 flex items-center justify-between">
                <span>Whisper Model</span>
                {selectedModelData?.is_installed && (
                  <span className="text-emerald-400 font-normal flex items-center gap-1 text-[11px]">
                    <CheckCircle2 className="w-3 h-3" /> Ready Offline ({selectedModelData.disk_size_mb} MB)
                  </span>
                )}
              </label>
              <ModelSelector
                models={models}
                selectedModel={selectedModel}
                onSelectModel={setSelectedModel}
              />
              {selectedModelData && (
                <p className="text-[11px] text-zinc-400 mt-1">
                  {selectedModelData.description}
                </p>
              )}
            </div>

            {/* Language Selection */}
            <div>
              <label className="block text-zinc-300 font-medium mb-1">Spoken Language</label>
              <LanguageSelector
                value={selectedLanguage}
                onChange={setSelectedLanguage}
              />
              <p className="text-[11px] text-zinc-500 mt-1">
                Auto-detect will inspect the first 30 seconds to determine speech language.
              </p>
            </div>

            {/* Device & Hardware */}
            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-zinc-800">
              <div>
                <label className="block text-zinc-300 font-medium mb-1">Inference Device</label>
                <select
                  value={selectedDevice}
                  onChange={(e) => setSelectedDevice(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="auto">Auto (CUDA / CPU Fallback)</option>
                  <option value="cuda">NVIDIA GPU (CUDA)</option>
                  <option value="cpu">CPU (Multi-threaded int8)</option>
                </select>
              </div>

              <div>
                <label className="block text-zinc-300 font-medium mb-1">VAD Filtering</label>
                <button
                  type="button"
                  onClick={() => setVadFilter(!vadFilter)}
                  className={`w-full py-1.5 px-3 rounded-lg border text-left flex items-center justify-between transition-colors ${
                    vadFilter
                      ? 'bg-indigo-600/10 border-indigo-500/30 text-indigo-300'
                      : 'bg-zinc-950 border-zinc-800 text-zinc-400'
                  }`}
                >
                  <span>Voice Filter (VAD)</span>
                  <span className="font-mono text-[10px]">{vadFilter ? 'ON' : 'OFF'}</span>
                </button>
              </div>
            </div>

            {/* Word Timestamps */}
            <div className="flex items-center justify-between p-2.5 bg-zinc-950/60 rounded-lg border border-zinc-800/80">
              <div>
                <span className="text-zinc-200 font-medium block">Word-Level Timestamps</span>
                <span className="text-[11px] text-zinc-500">
                  Required for animated caption karaoke and word seeking.
                </span>
              </div>
              <input
                type="checkbox"
                checked={wordTimestamps}
                onChange={(e) => setWordTimestamps(e.target.checked)}
                className="w-4 h-4 accent-indigo-600 rounded cursor-pointer"
              />
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-2 pt-4 border-t border-zinc-800">
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors flex items-center gap-1.5 shadow-lg shadow-indigo-600/20 disabled:opacity-50"
              >
                {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {isRetranscribe ? 'Retranscribe' : 'Start Transcription'}
              </button>
            </div>
          </>
        )}
      </form>
    </Modal>
  );
};
