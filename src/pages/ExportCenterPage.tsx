import React, { useEffect, useState } from 'react';
import {
  Download,
  FolderOpen,
  Play,
  Trash2,
  Film,
  HardDrive,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  X,
} from 'lucide-react';
import { api, ExportData } from '../services/api';

interface ExportCenterPageProps {
  onNavigateToStudio?: () => void;
}

export const ExportCenterPage: React.FC<ExportCenterPageProps> = ({ onNavigateToStudio }) => {
  const [exportsList, setExportsList] = useState<ExportData[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [previewExport, setPreviewExport] = useState<ExportData | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    loadExports();
  }, []);

  const loadExports = async () => {
    setIsLoading(true);
    try {
      const res = await api.listAllExports();
      setExportsList(res);
    } catch (err: any) {
      console.error('Failed to load exports:', err);
      setStatusMessage('Unable to fetch exports. Ensure the backend engine is running.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenFolder = async (outputPath?: string) => {
    if (!outputPath) {
      setStatusMessage('File path is not available.');
      return;
    }
    if (window.electronAPI?.showItemInFolder) {
      await window.electronAPI.showItemInFolder(outputPath);
    } else {
      setStatusMessage(`Output path: ${outputPath}`);
    }
  };

  const handleDelete = async (exportId: string) => {
    if (!confirm('Are you sure you want to delete this rendered export? This cannot be undone.')) return;
    try {
      await api.deleteExport(exportId);
      setExportsList((prev) => prev.filter((e) => e.id !== exportId));
      setStatusMessage('Export deleted successfully.');
    } catch (err: any) {
      setStatusMessage(`Failed to delete export: ${err?.message || 'Unknown error'}`);
    }
  };

  const totalSizeMb = exportsList.reduce((acc, curr) => acc + (curr.file_size_bytes ? curr.file_size_bytes / (1024 * 1024) : 0), 0);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-5 border-b border-[#1f1f2b]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
              <Film className="w-6 h-6 text-indigo-400" />
              Export Center
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold uppercase tracking-wider">
              {exportsList.length} Rendered Clips
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Access, inspect, preview, and reveal rendered 9:16 portrait videos ready for distribution on TikTok, Instagram Reels, and YouTube Shorts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadExports}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 bg-[#1a1a24] hover:bg-[#222232] border border-[#2b2b3d] text-zinc-200 text-xs font-semibold rounded-xl transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {onNavigateToStudio && (
            <button
              onClick={onNavigateToStudio}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/30 transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
              New 9:16 Render
            </button>
          )}
        </div>
      </div>

      {/* Status banner */}
      {statusMessage && (
        <div className="p-3 bg-[#161622] border border-[#262638] rounded-xl flex items-center justify-between text-xs text-zinc-300">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-indigo-400 flex-shrink-0" />
            <span>{statusMessage}</span>
          </div>
          <button onClick={() => setStatusMessage(null)} className="text-zinc-500 hover:text-zinc-300 text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* 2. Top Stats Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 bg-[#121218] border border-[#1f1f2b] rounded-2xl flex items-center gap-3.5">
          <div className="h-10 w-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Film className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Total Rendered Clips</span>
            <div className="text-xl font-black text-white">{exportsList.length}</div>
          </div>
        </div>

        <div className="p-4 bg-[#121218] border border-[#1f1f2b] rounded-2xl flex items-center gap-3.5">
          <div className="h-10 w-10 rounded-xl bg-emerald-600/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <HardDrive className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Total Storage Occupied</span>
            <div className="text-xl font-black text-white">{totalSizeMb.toFixed(1)} MB</div>
          </div>
        </div>

        <div className="p-4 bg-[#121218] border border-[#1f1f2b] rounded-2xl flex items-center gap-3.5">
          <div className="h-10 w-10 rounded-xl bg-amber-600/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Quality Standard</span>
            <div className="text-xl font-black text-white">1080p 60fps NVENC</div>
          </div>
        </div>
      </div>

      {/* 3. Exports Grid */}
      {exportsList.length === 0 ? (
        <div className="p-12 text-center bg-[#121218] border border-[#1f1f2b] rounded-2xl space-y-3">
          <Film className="w-12 h-12 text-zinc-600 mx-auto" />
          <h3 className="text-sm font-bold text-zinc-200">No Rendered Clips Yet</h3>
          <p className="text-xs text-zinc-400 max-w-md mx-auto">
            You haven't rendered any final composition exports yet. Head over to the Composition Studio or Project Studio to reframe a highlight clip.
          </p>
          {onNavigateToStudio && (
            <button
              onClick={onNavigateToStudio}
              className="mt-2 inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Go to Composition Studio
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {exportsList.map((exp) => {
            const fileName = exp.output_path ? exp.output_path.split(/[\\/]/).pop() : `export_${exp.id.slice(0, 8)}.mp4`;
            const sizeMb = exp.file_size_bytes ? (exp.file_size_bytes / (1024 * 1024)).toFixed(1) : 'Unknown';

            return (
              <div
                key={exp.id}
                className="bg-[#121218] border border-[#1f1f2b] hover:border-indigo-500/40 rounded-2xl p-4 flex flex-col justify-between space-y-4 transition-all group"
              >
                {/* Top preview frame / thumbnail */}
                <div className="relative aspect-[9/16] max-h-56 w-full mx-auto bg-black rounded-xl overflow-hidden border border-zinc-800 flex items-center justify-center">
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10" />
                  <Film className="w-8 h-8 text-zinc-600 group-hover:text-indigo-400 transition" />

                  {/* Play Overlay Button */}
                  <button
                    onClick={() => setPreviewExport(exp)}
                    className="absolute z-20 h-10 w-10 rounded-full bg-indigo-600/90 hover:bg-indigo-500 text-white flex items-center justify-center shadow-lg transition"
                  >
                    <Play className="w-4 h-4 ml-0.5" />
                  </button>

                  <div className="absolute bottom-2 left-2 z-20">
                    <span className="px-2 py-0.5 rounded bg-black/70 text-[10px] font-mono text-zinc-200">
                      {exp.resolution || '1080x1920'}
                    </span>
                  </div>

                  <div className="absolute bottom-2 right-2 z-20">
                    <span className="px-2 py-0.5 rounded bg-black/70 text-[10px] font-mono text-zinc-200">
                      {sizeMb} MB
                    </span>
                  </div>
                </div>

                {/* Details */}
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-zinc-100 truncate" title={fileName}>
                    {fileName}
                  </h4>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
                    <span>{exp.created_at ? new Date(exp.created_at).toLocaleDateString() : 'Recent'}</span>
                    <span>•</span>
                    <span>{exp.status || 'completed'}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#1f1f2b]">
                  <button
                    onClick={() => handleOpenFolder(exp.output_path)}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 bg-[#171722] hover:bg-[#20202e] border border-[#242436] rounded-xl text-[11px] font-semibold text-zinc-300 transition"
                    title="Reveal in Windows Explorer"
                  >
                    <FolderOpen className="w-3.5 h-3.5 text-zinc-400" />
                    <span>Folder</span>
                  </button>

                  <a
                    href={api.getExportDownloadUrl(exp.id)}
                    download
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 bg-[#171722] hover:bg-[#20202e] border border-[#242436] rounded-xl text-[11px] font-semibold text-zinc-300 transition"
                    title="Download Video File"
                  >
                    <Download className="w-3.5 h-3.5 text-zinc-400" />
                    <span>Save</span>
                  </a>

                  <button
                    onClick={() => handleDelete(exp.id)}
                    className="flex items-center justify-center gap-1.5 py-1.5 px-2 bg-rose-950/20 hover:bg-rose-900/30 border border-rose-800/30 rounded-xl text-[11px] font-semibold text-rose-400 transition"
                    title="Delete Export"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Preview Modal */}
      {previewExport && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#121218] border border-[#252538] rounded-2xl max-w-lg w-full p-4 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-2 border-b border-[#1f1f2b]">
              <span className="text-xs font-bold text-zinc-200 truncate">
                {previewExport.output_path?.split(/[\\/]/).pop()}
              </span>
              <button
                onClick={() => setPreviewExport(null)}
                className="text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="relative aspect-[9/16] max-h-[70vh] mx-auto bg-black rounded-xl overflow-hidden border border-zinc-800">
              <video
                src={api.getExportStreamUrl(previewExport.id)}
                controls
                autoPlay
                className="w-full h-full object-contain"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2 border-t border-[#1f1f2b]">
              <button
                onClick={() => handleOpenFolder(previewExport.output_path)}
                className="flex items-center gap-2 px-3 py-1.5 bg-[#171722] hover:bg-[#222232] border border-[#242436] rounded-xl text-xs font-semibold text-zinc-300 transition"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                Show in Explorer
              </button>
              <button
                onClick={() => setPreviewExport(null)}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};