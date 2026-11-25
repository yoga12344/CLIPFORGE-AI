import React, { useEffect, useState } from 'react';
import {
  Settings,
  HardDrive,
  Cpu,
  Bot,
  Sliders,
  Save,
  CheckCircle2,
  FolderOpen,
  RotateCcw
} from 'lucide-react';
import { useSettingsStore } from '../store/settingsStore';
import { useSystemStore } from '../store/systemStore';

export const SettingsPage: React.FC = () => {
  const { settings, fetchSettings, updateSettings, isSaving } = useSettingsStore();
  const { diskPercent, diskUsedGb, diskTotalGb } = useSystemStore() as any;

  const [activeTab, setActiveTab] = useState<'general' | 'storage' | 'performance' | 'ai'>('general');
  const [form, setForm] = useState<Record<string, any>>({});

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  useEffect(() => {
    if (settings) {
      setForm(settings);
    }
  }, [settings]);

  const handleChange = (key: string, value: any) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    await updateSettings(form);
  };

  const tabs = [
    { id: 'general', label: 'General', icon: Sliders },
    { id: 'storage', label: 'Storage & Paths', icon: HardDrive },
    { id: 'performance', label: 'Hardware Acceleration', icon: Cpu },
    { id: 'ai', label: 'Local AI Models', icon: Bot },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            <Settings className="w-6 h-6 text-indigo-400" />
            Application Settings
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Configure local resource limits, directories, and hardware acceleration preferences.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-600/20 flex items-center gap-2 transition cursor-pointer"
        >
          <Save className="w-4 h-4" />
          {isSaving ? 'Saving...' : 'Save Preferences'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex bg-[#14141d] p-1 rounded-2xl border border-[#20202e]">
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-bold rounded-xl transition ${
                isActive
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab Contents */}
      <div className="bg-[#14141d] border border-[#20202e] rounded-2xl p-6 space-y-6">
        {/* 1. GENERAL */}
        {activeTab === 'general' && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-white">General Preferences</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Theme Mode</label>
                <select
                  value={form.theme || 'dark'}
                  onChange={(e) => handleChange('theme', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="dark">Dark Charcoal (Default)</option>
                  <option value="system">Follow System</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Default Language</label>
                <select
                  value={form.language || 'en'}
                  onChange={(e) => handleChange('language', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="en">English (US)</option>
                  <option value="es">Spanish</option>
                  <option value="de">German</option>
                  <option value="fr">French</option>
                  <option value="auto">Auto Detect</option>
                </select>
              </div>
            </div>

            <div className="space-y-1.5 pt-2">
              <label className="text-xs font-semibold text-zinc-300">Startup View</label>
              <select
                value={form.startup_behavior || 'dashboard'}
                onChange={(e) => handleChange('startup_behavior', e.target.value)}
                className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
              >
                <option value="dashboard">Dashboard Overview</option>
                <option value="projects">Projects Library</option>
                <option value="create">Direct Video Import</option>
              </select>
            </div>
          </div>
        )}

        {/* 2. STORAGE */}
        {activeTab === 'storage' && (
          <div className="space-y-5">
            <h3 className="text-sm font-bold text-white">Storage Directories</h3>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Projects Directory</label>
                <input
                  type="text"
                  value={form.project_storage_path || ''}
                  onChange={(e) => handleChange('project_storage_path', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-zinc-300 font-mono focus:outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Export Directory</label>
                <input
                  type="text"
                  value={form.export_directory || ''}
                  onChange={(e) => handleChange('export_directory', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-zinc-300 font-mono focus:outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Cache & Temp Directory</label>
                <input
                  type="text"
                  value={form.cache_path || ''}
                  onChange={(e) => handleChange('cache_path', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-zinc-300 font-mono focus:outline-none"
                />
              </div>
            </div>

            <div className="p-3.5 bg-[#191924] rounded-xl border border-[#272738] space-y-2">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-zinc-300">Storage Usage</span>
                <span className="font-mono text-zinc-400">
                  {diskUsedGb} GB / {diskTotalGb} GB ({diskPercent}% Used)
                </span>
              </div>
              <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full"
                  style={{ width: `${Math.min(diskPercent || 0, 100)}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* 3. PERFORMANCE */}
        {activeTab === 'performance' && (
          <div className="space-y-5">
            <h3 className="text-sm font-bold text-white">Hardware & VRAM Allocation</h3>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-3.5 bg-[#191924] rounded-xl border border-[#272738]">
                <div>
                  <h4 className="text-xs font-bold text-white">Hardware GPU Acceleration (NVENC)</h4>
                  <p className="text-[11px] text-zinc-400">
                    Use NVIDIA RTX 4060 hardware encoder for video scaling and H.264 exporting.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={form.gpu_acceleration ?? true}
                  onChange={(e) => handleChange('gpu_acceleration', e.target.checked)}
                  className="rounded border-zinc-700 text-indigo-600 focus:ring-0 h-4 w-4"
                />
              </div>

              <div className="flex items-center justify-between p-3.5 bg-[#191924] rounded-xl border border-[#272738]">
                <div>
                  <h4 className="text-xs font-bold text-white">Automatic CPU Fallback</h4>
                  <p className="text-[11px] text-zinc-400">
                    Fall back to CPU inference if VRAM is temporarily constrained.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={form.cpu_fallback ?? true}
                  onChange={(e) => handleChange('cpu_fallback', e.target.checked)}
                  className="rounded border-zinc-700 text-indigo-600 focus:ring-0 h-4 w-4"
                />
              </div>

              <div className="space-y-2 p-3.5 bg-[#191924] rounded-xl border border-[#272738]">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-zinc-300">GPU VRAM Budget Limit</span>
                  <span className="font-mono text-indigo-400 font-bold">{form.vram_budget_mb || 6000} MB</span>
                </div>
                <input
                  type="range"
                  min="2048"
                  max="8000"
                  step="256"
                  value={form.vram_budget_mb || 6000}
                  onChange={(e) => handleChange('vram_budget_mb', Number(e.target.value))}
                  className="w-full accent-indigo-500"
                />
                <p className="text-[10px] text-zinc-500">
                  Caps local AI model loading to prevent VRAM Out-Of-Memory exceptions on 8 GB cards.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* 4. AI MODELS */}
        {activeTab === 'ai' && (
          <div className="space-y-5">
            <h3 className="text-sm font-bold text-white">Default Local AI Models</h3>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Speech-To-Text Model</label>
                <select
                  value={form.default_transcription_model || 'whisper-base-int8'}
                  onChange={(e) => handleChange('default_transcription_model', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="whisper-tiny-int8">Whisper Tiny (Fastest, ~75MB)</option>
                  <option value="whisper-base-int8">Whisper Base int8 (Balanced, ~140MB - Recommended)</option>
                  <option value="whisper-small-int8">Whisper Small int8 (Accurate, ~460MB)</option>
                  <option value="whisper-medium-int8">Whisper Medium int8 (High Quality, ~1.5GB)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Highlight Detection LLM</label>
                <select
                  value={form.default_llm_model || 'llama-3.2-3b-instruct'}
                  onChange={(e) => handleChange('default_llm_model', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="llama-3.2-3b-instruct">Llama 3.2 3B Instruct (4-bit, ~2.0GB VRAM)</option>
                  <option value="qwen-2.5-3b-instruct">Qwen 2.5 3B Instruct (4-bit, ~2.1GB VRAM)</option>
                  <option value="mistral-7b-instruct">Mistral 7B Instruct (4-bit, ~4.5GB VRAM)</option>
                  <option value="heuristic-rules">Heuristic Rule-Based Engine (Zero VRAM)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-zinc-300">Model Weights Directory</label>
                <input
                  type="text"
                  value={form.model_storage_location || ''}
                  onChange={(e) => handleChange('model_storage_location', e.target.value)}
                  className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-zinc-300 font-mono focus:outline-none"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
