import React, { useState, useEffect } from 'react';
import {
  Upload,
  FileVideo,
  CheckCircle2,
  AlertCircle,
  Clock,
  Film,
  Volume2,
  HardDrive,
  Layers,
  ArrowRight,
  FolderPlus,
  Loader2,
  X
} from 'lucide-react';
import { api, VideoProbeData, ProjectData } from '../services/api';
import { useProjectStore } from '../store/projectStore';
import { useToastStore } from '../store/toastStore';

interface VideoImportProps {
  initialProjectId?: string | null;
  onImportComplete: (projectId: string, videoId: string) => void;
}

export const VideoImport: React.FC<VideoImportProps> = ({
  initialProjectId,
  onImportComplete,
}) => {
  const { projects, fetchProjects, createProject } = useProjectStore();
  const showToast = useToastStore((s) => s.show);

  const [selectedProjectId, setSelectedProjectId] = useState<string>(initialProjectId || '');
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [isProbing, setIsProbing] = useState<boolean>(false);
  const [probeResult, setProbeResult] = useState<VideoProbeData | null>(null);
  const [probeError, setProbeError] = useState<string | null>(null);

  // Import options
  const [copyToStorage, setCopyToStorage] = useState<boolean>(true);
  const [isImporting, setIsImporting] = useState<boolean>(false);

  // New project inline
  const [isCreatingInline, setIsCreatingInline] = useState(false);
  const [inlineProjectName, setInlineProjectName] = useState('');

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const handleFilePicked = async (filePath: string) => {
    setSelectedFilePath(filePath);
    setIsProbing(true);
    setProbeError(null);
    setProbeResult(null);

    try {
      const probe = await api.probeVideo(filePath);
      if (!probe.valid) {
        setProbeError(probe.error || 'Failed to decode video file');
      } else {
        setProbeResult(probe);
      }
    } catch (err: any) {
      setProbeError(err.message || 'Error executing FFprobe inspection');
    } finally {
      setIsProbing(false);
    }
  };

  const handleNativeDialog = async () => {
    if (window.electronAPI?.openVideoDialog) {
      const res = await window.electronAPI.openVideoDialog();
      if (!res.canceled && res.filePaths.length > 0) {
        handleFilePicked(res.filePaths[0]);
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      // In Electron / Chromium, File.path gives the absolute path
      const filePath = (file as any).path;
      if (filePath) {
        handleFilePicked(filePath);
      } else {
        showToast('error', 'Path Error', 'Cannot determine local file path from browser drag.');
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleImportSubmit = async () => {
    if (!probeResult || !selectedProjectId) return;
    setIsImporting(true);

    try {
      const video = await api.importVideo(selectedProjectId, probeResult.file_path, copyToStorage);
      showToast('success', 'Video Imported', `"${video.filename}" successfully added to project.`);
      onImportComplete(selectedProjectId, video.id);
    } catch (err: any) {
      showToast('error', 'Import Failed', err.message);
    } finally {
      setIsImporting(false);
    }
  };

  const handleInlineProjectCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inlineProjectName.trim()) return;
    try {
      const p = await createProject(inlineProjectName.trim());
      setSelectedProjectId(p.id);
      setIsCreatingInline(false);
      setInlineProjectName('');
    } catch (err) {}
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
          <Upload className="w-6 h-6 text-indigo-400" />
          Import Video
        </h1>
        <p className="text-xs text-zinc-400 mt-1">
          Inspect source landscape video with FFprobe and ingest into SQLite repository.
        </p>
      </div>

      {/* Target Project Assignment */}
      <div className="p-4 bg-[#14141d] border border-[#20202e] rounded-2xl space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-zinc-300">Target Project</label>
          {!isCreatingInline && (
            <button
              onClick={() => setIsCreatingInline(true)}
              className="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold cursor-pointer"
            >
              + Create new project
            </button>
          )}
        </div>

        {isCreatingInline ? (
          <form onSubmit={handleInlineProjectCreate} className="flex gap-2">
            <input
              type="text"
              placeholder="New project title..."
              value={inlineProjectName}
              onChange={(e) => setInlineProjectName(e.target.value)}
              className="flex-1 bg-[#1b1b26] border border-[#272738] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
              autoFocus
            />
            <button
              type="submit"
              className="px-3.5 py-2 bg-indigo-600 text-white font-bold text-xs rounded-xl"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setIsCreatingInline(false)}
              className="px-3 py-2 bg-[#1f1f2e] text-zinc-400 text-xs rounded-xl"
            >
              Cancel
            </button>
          </form>
        ) : (
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="w-full bg-[#1b1b26] border border-[#272738] text-xs rounded-xl px-3 py-2.5 text-zinc-200 focus:outline-none focus:border-indigo-500"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.video_count} videos)
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Drop Zone Area */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        className="p-10 border-2 border-dashed border-[#272738] hover:border-indigo-500/80 rounded-2xl text-center space-y-4 bg-[#14141d]/50 transition cursor-pointer relative"
        onClick={handleNativeDialog}
      >
        <div className="h-12 w-12 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto">
          <Upload className="w-6 h-6" />
        </div>

        <div className="space-y-1">
          <p className="text-sm font-bold text-white">
            Drag and drop your video file here, or click to browse
          </p>
          <p className="text-xs text-zinc-400">
            Supports MP4, MOV, MKV, WebM and AVI up to 4K resolution
          </p>
        </div>

        <button
          type="button"
          className="px-4 py-2 bg-[#1f1f2e] hover:bg-[#272738] text-xs font-semibold rounded-xl text-zinc-300 border border-[#2d2d40] transition"
        >
          Select Video from Computer
        </button>
      </div>

      {/* Loading Probe Indicator */}
      {isProbing && (
        <div className="p-4 bg-[#14141d] border border-[#20202e] rounded-2xl flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
          <span className="text-xs text-zinc-300">
            Inspecting technical video streams with FFprobe...
          </span>
        </div>
      )}

      {/* Probe Error */}
      {probeError && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-rose-300">
            <strong className="block text-white">Validation Error:</strong>
            {probeError}
          </div>
        </div>
      )}

      {/* Validated Metadata Card */}
      {probeResult && probeResult.valid && (
        <div className="p-6 bg-[#14141d] border border-[#20202e] rounded-2xl space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-[#1c1c28]">
            <div className="flex items-center gap-2.5">
              <FileVideo className="w-5 h-5 text-indigo-400" />
              <div>
                <h4 className="text-sm font-bold text-white truncate max-w-md">
                  {probeResult.filename}
                </h4>
                <p className="text-[11px] text-zinc-500 truncate max-w-lg font-mono">
                  {probeResult.file_path}
                </p>
              </div>
            </div>

            <button
              onClick={() => {
                setProbeResult(null);
                setSelectedFilePath(null);
              }}
              className="p-1 rounded text-zinc-500 hover:text-zinc-300"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-[#191924] rounded-xl border border-[#232332] space-y-1">
              <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider block">
                Duration
              </span>
              <span className="text-sm font-extrabold text-white flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-indigo-400" />
                {formatDuration(probeResult.duration_seconds)}
              </span>
            </div>

            <div className="p-3 bg-[#191924] rounded-xl border border-[#232332] space-y-1">
              <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider block">
                Resolution & FPS
              </span>
              <span className="text-sm font-extrabold text-white flex items-center gap-1.5">
                <Film className="w-3.5 h-3.5 text-indigo-400" />
                {probeResult.width}x{probeResult.height} ({probeResult.fps} fps)
              </span>
            </div>

            <div className="p-3 bg-[#191924] rounded-xl border border-[#232332] space-y-1">
              <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider block">
                Video / Audio Codec
              </span>
              <span className="text-sm font-extrabold text-white truncate block">
                {probeResult.video_codec?.toUpperCase()} / {probeResult.audio_codec?.toUpperCase() || 'No Audio'}
              </span>
            </div>

            <div className="p-3 bg-[#191924] rounded-xl border border-[#232332] space-y-1">
              <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider block">
                File Size
              </span>
              <span className="text-sm font-extrabold text-white flex items-center gap-1.5">
                <HardDrive className="w-3.5 h-3.5 text-indigo-400" />
                {formatBytes(probeResult.file_size_bytes)}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-300">
              <input
                type="checkbox"
                checked={copyToStorage}
                onChange={(e) => setCopyToStorage(e.target.checked)}
                className="rounded border-zinc-700 text-indigo-600 focus:ring-0"
              />
              <span>Copy file to ClipForge managed storage (keeps original safe)</span>
            </label>

            <button
              onClick={handleImportSubmit}
              disabled={isImporting || !selectedProjectId}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-600/20 flex items-center gap-2 transition cursor-pointer"
            >
              {isImporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Ingesting Video...
                </>
              ) : (
                <>
                  <span>Import & Continue</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
