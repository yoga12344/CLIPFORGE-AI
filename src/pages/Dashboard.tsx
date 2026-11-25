import React, { useEffect, useState } from 'react';
import {
  Upload,
  Film,
  Scissors,
  CheckCircle2,
  HardDrive,
  Cpu,
  Layers,
  Sparkles,
  ArrowRight,
  FolderPlus,
  Clock,
  ChevronRight
} from 'lucide-react';
import { useSystemStore } from '../store/systemStore';
import { useProjectStore } from '../store/projectStore';
import { Modal } from '../components/ui/Modal';

interface DashboardProps {
  onNavigateToCreate: () => void;
  onNavigateToProjects: () => void;
  onSelectProject: (id: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  onNavigateToCreate,
  onNavigateToProjects,
  onSelectProject,
}) => {
  const {
    isBackendConnected,
    isDbConnected,
    gpuName,
    hasGpu,
    vramUsedMb,
    vramTotalMb,
    vramPercent,
    cpuPercent,
    cpuCores,
    ramUsedGb,
    ramTotalGb,
    ramPercent,
    diskUsedGb,
    diskTotalGb,
    diskPercent,
    storageDir,
    nvencAvailable,
  } = useSystemStore() as any;

  const { dashboardStats, fetchDashboardStats, createProject } = useProjectStore();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchDashboardStats();
    const interval = setInterval(fetchDashboardStats, 5000);
    return () => clearInterval(interval);
  }, [fetchDashboardStats]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    setIsSubmitting(true);
    try {
      const proj = await createProject(newProjectName.trim(), newProjectDesc.trim());
      setIsCreateModalOpen(false);
      setNewProjectName('');
      setNewProjectDesc('');
      onSelectProject(proj.id);
    } finally {
      setIsSubmitting(false);
    }
  };

  const statCards = [
    {
      label: 'Total Projects',
      value: dashboardStats?.total_projects ?? 0,
      icon: FolderPlus,
      note: 'Active in SQLite'
    },
    {
      label: 'Imported Videos',
      value: dashboardStats?.total_videos ?? 0,
      icon: Film,
      note: 'Source media files'
    },
    {
      label: 'Generated Clips',
      value: dashboardStats?.total_clips ?? 0,
      icon: Scissors,
      note: '9:16 Vertical Shorts'
    },
    {
      label: 'Completed Exports',
      value: dashboardStats?.total_exports ?? 0,
      icon: CheckCircle2,
      note: 'Saved to disk'
    },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* 1. Header & Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">
            ClipForge AI Studio
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Local-first AI video repurposing engine with RTX 4060 hardware acceleration.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-3.5 py-2 bg-[#1b1b26] hover:bg-[#232332] text-zinc-200 font-semibold text-xs rounded-xl border border-[#272738] flex items-center gap-2 transition cursor-pointer"
          >
            <FolderPlus className="w-3.5 h-3.5 text-zinc-400" />
            New Project
          </button>
          <button
            onClick={onNavigateToCreate}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-600/20 flex items-center gap-2 transition cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5" />
            Import Video
          </button>
        </div>
      </div>

      {/* 2. Top Metric Cards (Real SQLite stats) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className="p-4 bg-[#14141d] border border-[#20202e] rounded-2xl space-y-1.5"
            >
              <div className="flex items-center justify-between text-zinc-400">
                <span className="text-xs font-semibold">{card.label}</span>
                <Icon className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="text-2xl font-black text-white">{card.value}</div>
              <div className="text-[10px] text-zinc-500">{card.note}</div>
            </div>
          );
        })}
      </div>

      {/* 3. Hardware Telemetry Panel (Real Data) */}
      <div className="p-6 bg-[#14141d] border border-[#20202e] rounded-2xl space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-bold text-white">Local Acceleration Engine</h3>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
            {hasGpu ? 'NVIDIA CUDA Ready' : 'CPU Inference'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-1">
          {/* GPU Telemetry */}
          <div className="space-y-2 p-3 bg-[#191924] rounded-xl border border-[#272738]">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-zinc-300">GPU Device</span>
              <span className="text-[10px] text-indigo-400 font-semibold">{nvencAvailable ? 'NVENC Active' : 'Standard'}</span>
            </div>
            <p className="text-sm font-extrabold text-white truncate">{gpuName}</p>
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-[10px] text-zinc-400">
                <span>VRAM Allocation</span>
                <span className="font-mono font-bold text-zinc-200">{vramUsedMb} / {vramTotalMb} MB ({vramPercent}%)</span>
              </div>
              <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full"
                  style={{ width: `${Math.min(vramPercent || 0, 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* CPU & Memory */}
          <div className="space-y-2 p-3 bg-[#191924] rounded-xl border border-[#272738]">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-zinc-300">Host Processor</span>
              <span className="text-[10px] text-zinc-400 font-mono">{cpuCores} Threads</span>
            </div>
            <p className="text-sm font-extrabold text-white">CPU Load: {cpuPercent}%</p>
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-[10px] text-zinc-400">
                <span>System RAM</span>
                <span className="font-mono font-bold text-zinc-200">{ramUsedGb} / {ramTotalGb} GB ({ramPercent}%)</span>
              </div>
              <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full"
                  style={{ width: `${Math.min(ramPercent || 0, 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* SQLite & Storage */}
          <div className="space-y-2 p-3 bg-[#191924] rounded-xl border border-[#272738]">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-zinc-300">SQLite Database</span>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${isDbConnected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                {isDbConnected ? 'Connected' : 'Offline'}
              </span>
            </div>
            <p className="text-xs font-mono text-zinc-400 truncate" title={storageDir}>
              {storageDir || 'storage/clipforge_data'}
            </p>
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-[10px] text-zinc-400">
                <span>Disk Storage ({diskPercent}% Used)</span>
                <span className="font-mono font-bold text-zinc-200">{diskUsedGb} / {diskTotalGb} GB</span>
              </div>
              <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full"
                  style={{ width: `${Math.min(diskPercent || 0, 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Recent Projects List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-400" />
            Recent Projects
          </h3>
          <button
            onClick={onNavigateToProjects}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1 transition cursor-pointer"
          >
            View all ({dashboardStats?.total_projects || 0})
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {dashboardStats && dashboardStats.recent_projects.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {dashboardStats.recent_projects.map((proj) => (
              <div
                key={proj.id}
                onClick={() => onSelectProject(proj.id)}
                className="p-4 bg-[#14141d] border border-[#20202e] hover:border-indigo-500/50 rounded-2xl cursor-pointer transition space-y-2.5 group"
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-white group-hover:text-indigo-400 transition truncate max-w-[200px]">
                    {proj.name}
                  </h4>
                  <span className="text-[10px] text-zinc-500 font-mono">
                    {new Date(proj.updated_at).toLocaleDateString()}
                  </span>
                </div>
                {proj.description && (
                  <p className="text-xs text-zinc-400 line-clamp-1">{proj.description}</p>
                )}
                <div className="flex items-center justify-between text-[11px] text-zinc-500 pt-2 border-t border-[#1c1c28]">
                  <span>{proj.video_count} videos</span>
                  <span className="text-indigo-400 font-semibold">{proj.clip_count} clips</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 border-2 border-dashed border-[#20202e] rounded-2xl text-center space-y-3 bg-[#14141d]/30">
            <p className="text-xs text-zinc-400">No projects created yet.</p>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold cursor-pointer"
            >
              + Create your first project
            </button>
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Project"
        description="Projects organize source videos, transcripts, generated clips, and EDL edits."
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-300">Project Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Creator Podcast Ep 14"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              className="w-full bg-[#1b1b26] border border-[#272738] focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-zinc-500 focus:outline-none"
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-300">Description (Optional)</label>
            <textarea
              placeholder="Brief context or notes for this clipping project..."
              value={newProjectDesc}
              onChange={(e) => setNewProjectDesc(e.target.value)}
              className="w-full bg-[#1b1b26] border border-[#272738] focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-zinc-500 focus:outline-none h-20 resize-none"
            />
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={() => setIsCreateModalOpen(false)}
              className="px-4 py-2 bg-[#1f1f2e] hover:bg-[#272738] text-xs font-semibold rounded-xl text-zinc-300 transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !newProjectName.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold rounded-xl text-white shadow-lg shadow-indigo-600/20 transition cursor-pointer"
            >
              {isSubmitting ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
