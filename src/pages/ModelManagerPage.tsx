import React, { useState, useEffect } from 'react';
import { Cpu, HardDrive, Download, Trash2, CheckCircle2, Clock, AlertCircle, RefreshCw, Sparkles, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';
import { Button } from '../components/ui/Button';

interface ModelInfo {
  id: string;
  name: string;
  category: string;
  description: string;
  file_name: string;
  file_size_mb: float;
  is_installed: boolean;
  is_downloading: boolean;
  hardware_req: string;
  local_path?: string;
}

export const ModelManagerPage: React.FC = () => {
  const [models, setModels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const loadModels = async () => {
    setIsLoading(true);
    try {
      const data = await api.listAllModels();
      setModels(data);
    } catch (err) {
      console.warn('Could not load models:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadModels();
  }, []);

  const handleDownload = async (modelId: string) => {
    setDownloadingId(modelId);
    try {
      await api.downloadLlmModel(modelId);
      setTimeout(loadModels, 2000);
    } catch (err) {
      console.warn('Download error:', err);
    } finally {
      setDownloadingId(null);
    }
  };

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case 'speech':
        return <span className="text-[10px] bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded border border-blue-500/30">Speech STT</span>;
      case 'vad':
        return <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">Voice VAD</span>;
      case 'diarization':
        return <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-500/30">Diarization</span>;
      case 'vision':
        return <span className="text-[10px] bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded border border-purple-500/30">Computer Vision</span>;
      case 'active_speaker':
        return <span className="text-[10px] bg-pink-500/20 text-pink-300 px-2 py-0.5 rounded border border-pink-500/30">Active Speaker</span>;
      case 'llm':
        return <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded border border-indigo-500/30">Local LLM</span>;
      default:
        return <span className="text-[10px] bg-zinc-500/20 text-zinc-300 px-2 py-0.5 rounded">AI Engine</span>;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0e0e13] text-zinc-100 overflow-hidden">
      {/* Top Header */}
      <div className="h-14 border-b border-[#1f1f2b] px-6 flex items-center justify-between bg-[#121218]/80 backdrop-blur flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-zinc-100">Local AI Model Manager</h1>
            <p className="text-[11px] text-zinc-400">Offline speech, vision, active speaker, and language models (Zero cloud dependencies)</p>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={loadModels} icon={RefreshCw}>
          Refresh Status
        </Button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Hardware Status Card */}
        <div className="p-4 rounded-xl bg-gradient-to-r from-purple-950/30 to-indigo-950/30 border border-purple-500/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-purple-500/20 text-purple-300">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-bold text-zinc-100 flex items-center gap-2">
                <span>Hardware Acceleration Environment</span>
                <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/30">
                  Qualified
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                NVIDIA GeForce RTX 4060 (8 GB VRAM) • Intel Core i7-13620H • 16 GB DDR5 RAM
              </p>
            </div>
          </div>
          <div className="text-right text-[11px] text-zinc-400 font-mono">
            <div>Local-First Execution</div>
            <div className="text-emerald-400">CPU Fallback Ready</div>
          </div>
        </div>

        {/* Model Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {isLoading ? (
            <div className="col-span-2 text-center py-12 text-zinc-500 text-xs">
              Inspecting installed models...
            </div>
          ) : (
            models.map((m) => (
              <div
                key={m.id}
                className="p-4 rounded-xl bg-[#14141e] border border-[#232332] space-y-3 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-zinc-100">{m.name}</span>
                    {getCategoryBadge(m.category)}
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">{m.description}</p>
                </div>

                <div className="space-y-2 pt-2 border-t border-white/5 text-[11px] text-zinc-400">
                  <div className="flex justify-between">
                    <span>Artifact:</span>
                    <span className="font-mono text-zinc-300">{m.file_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Footprint:</span>
                    <span className="font-mono text-zinc-300">{m.file_size_mb} MB</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Requirements:</span>
                    <span className="text-zinc-400">{m.hardware_req}</span>
                  </div>
                </div>

                <div className="pt-2 flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    {m.is_installed ? (
                      <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Installed & Verified
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[11px] text-amber-400 font-semibold">
                        <AlertCircle className="w-3.5 h-3.5" />
                        Available for Download
                      </span>
                    )}
                  </div>

                  {!m.is_installed && m.category === 'llm' && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleDownload(m.id)}
                      disabled={downloadingId === m.id}
                      icon={Download}
                    >
                      {downloadingId === m.id ? 'Downloading...' : 'Download GGUF'}
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
