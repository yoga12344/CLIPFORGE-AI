import React, { useEffect, useState } from 'react';
import {
  Film,
  Search,
  Plus,
  Play,
  Clock,
  HardDrive,
  Sparkles,
  ChevronRight,
  RefreshCw,
  FolderOpen,
  AlertCircle,
  FileVideo,
} from 'lucide-react';
import { api, VideoData, ProjectData } from '../services/api';

interface VideoLibraryPageProps {
  onOpenProject?: (projectId: string) => void;
  onNavigateToImport?: () => void;
  onNavigateToStudio?: () => void;
}

export const VideoLibraryPage: React.FC<VideoLibraryPageProps> = ({
  onOpenProject,
  onNavigateToImport,
  onNavigateToStudio,
}) => {
  const [videos, setVideos] = useState<VideoData[]>([]);
  const [projects, setProjects] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    loadLibrary();
  }, []);

  const loadLibrary = async () => {
    setIsLoading(true);
    try {
      const [vidsRes, projsRes] = await Promise.allSettled([
        api.listAllVideos(),
        api.getProjects(),
      ]);

      if (vidsRes.status === 'fulfilled') {
        setVideos(vidsRes.value);
      }
      if (projsRes.status === 'fulfilled') {
        const pMap: Record<string, string> = {};
        projsRes.value.forEach((p: ProjectData) => {
          pMap[p.id] = p.name;
        });
        setProjects(pMap);
      }
    } catch (err: any) {
      console.error('Error loading video library:', err);
      setStatusMessage('Unable to load video library.');
    } finally {
      setIsLoading(false);
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const filteredVideos = videos.filter((v) =>
    (v.filename || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-5 border-b border-[#1f1f2b]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
              <Film className="w-6 h-6 text-indigo-400" />
              Video Asset Library
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-[10px] font-bold uppercase tracking-wider">
              {videos.length} Source Videos
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Browse and manage all source recordings, podcasts, interviews, and gameplay videos imported into ClipForge AI.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadLibrary}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 bg-[#1a1a24] hover:bg-[#222232] border border-[#2b2b3d] text-zinc-200 text-xs font-semibold rounded-xl transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {onNavigateToImport && (
            <button
              onClick={onNavigateToImport}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-600/30 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Import Video
            </button>
          )}
        </div>
      </div>

      {/* 2. Search & Filters Bar */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search videos by file name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#121218] border border-[#1f1f2b] focus:border-indigo-500 rounded-xl pl-10 pr-4 py-2 text-xs text-zinc-200 placeholder-zinc-500 transition outline-none"
          />
        </div>
      </div>

      {/* 3. Video Grid */}
      {filteredVideos.length === 0 ? (
        <div className="p-12 text-center bg-[#121218] border border-[#1f1f2b] rounded-2xl space-y-3">
          <FileVideo className="w-12 h-12 text-zinc-600 mx-auto" />
          <h3 className="text-sm font-bold text-zinc-200">No Videos Found</h3>
          <p className="text-xs text-zinc-400 max-w-md mx-auto">
            {searchQuery ? 'No videos matched your search query.' : 'Import your first long-form video file to begin automated clipping.'}
          </p>
          {onNavigateToImport && !searchQuery && (
            <button
              onClick={onNavigateToImport}
              className="mt-2 inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Import Video File
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredVideos.map((vid) => {
            const sizeMb = (vid.file_size_bytes / (1024 * 1024)).toFixed(1);
            const projectName = projects[vid.project_id] || 'Default Project';

            return (
              <div
                key={vid.id}
                className="bg-[#121218] border border-[#1f1f2b] hover:border-indigo-500/40 rounded-2xl p-4 flex flex-col justify-between space-y-4 transition-all group"
              >
                {/* 16:9 Thumbnail representation */}
                <div className="relative aspect-video w-full bg-black rounded-xl overflow-hidden border border-zinc-800 flex items-center justify-center">
                  <Film className="w-8 h-8 text-zinc-600 group-hover:text-indigo-400 transition" />
                  <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/70 text-[10px] font-mono text-zinc-200">
                    {vid.width || 1920} × {vid.height || 1080}
                  </div>
                  <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/70 text-[10px] font-mono text-zinc-200 flex items-center gap-1">
                    <Clock className="w-3 h-3 text-zinc-400" />
                    {formatDuration(vid.duration_seconds)}
                  </div>
                </div>

                {/* Video details */}
                <div className="space-y-1.5">
                  <h4 className="text-xs font-bold text-zinc-100 truncate" title={vid.filename}>
                    {vid.filename}
                  </h4>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-400">
                    <span className="px-1.5 py-0.5 rounded bg-[#171722] border border-[#242436] font-medium text-zinc-300">
                      {projectName}
                    </span>
                    <span>•</span>
                    <span className="font-mono">{sizeMb} MB</span>
                    <span>•</span>
                    <span className="font-mono">{vid.fps || 30} FPS</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#1f1f2b]">
                  {onOpenProject && (
                    <button
                      onClick={() => onOpenProject(vid.project_id)}
                      className="flex items-center justify-center gap-1.5 py-1.5 px-2 bg-[#171722] hover:bg-[#20202e] border border-[#242436] rounded-xl text-[11px] font-semibold text-zinc-300 transition"
                    >
                      <Film className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Studio</span>
                    </button>
                  )}

                  {onNavigateToStudio && (
                    <button
                      onClick={onNavigateToStudio}
                      className="flex items-center justify-center gap-1.5 py-1.5 px-2 bg-indigo-600/15 hover:bg-indigo-600/25 border border-indigo-500/30 rounded-xl text-[11px] font-semibold text-indigo-300 transition"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Reframe 9:16</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};