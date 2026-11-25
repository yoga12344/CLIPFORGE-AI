import React, { useEffect } from 'react';
import {
  LayoutDashboard,
  FolderKanban,
  Wand2,
  Film,
  Sparkles,
  Palette,
  Cpu,
  ListOrdered,
  Layers,
  Activity,
  Settings,
  Minus,
  Square,
  X,
  HardDrive,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { useSystemStore } from '../../store/systemStore';

export type NavItem =
  | 'dashboard'
  | 'projects'
  | 'library'
  | 'create'
  | 'studio'
  | 'templates'
  | 'exports'
  | 'models'
  | 'queue'
  | 'diagnostics'
  | 'settings';

interface AppLayoutProps {
  activeNav: NavItem;
  onNavigate: (nav: NavItem) => void;
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  activeNav,
  onNavigate,
  children,
}) => {
  const {
    isBackendConnected,
    isDbConnected,
    gpuName,
    vramUsedMb,
    vramTotalMb,
    vramPercent,
    cpuPercent,
    ramPercent,
    ramUsedGb,
    ramTotalGb,
    diskPercent,
    diskFreeGb,
    appVersion,
    fetchStatus,
  } = useSystemStore() as any;

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'projects', label: 'Projects', icon: FolderKanban },
    { id: 'library', label: 'Video Library', icon: Film },
    { id: 'create', label: 'Import Video', icon: Wand2 },
    { id: 'studio', label: 'Composition Studio', icon: Sparkles },
    { id: 'templates', label: 'Subtitle Styles', icon: Palette },
    { id: 'exports', label: 'Export Center', icon: Layers },
    { id: 'models', label: 'AI Models', icon: Cpu },
    { id: 'queue', label: 'Processing Queue', icon: ListOrdered },
    { id: 'diagnostics', label: 'Diagnostics', icon: Activity },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#0e0e13] text-zinc-100 select-none">
      {/* 1. Custom Title Bar */}
      <header
        className="h-9 w-full bg-[#121218] border-b border-[#1f1f2b] flex items-center justify-between px-3 z-50 flex-shrink-0"
        style={{ WebkitAppRegion: 'drag' } as any}
      >
        <div className="flex items-center gap-2.5">
          <div className="h-4.5 w-4.5 rounded-md bg-indigo-600 flex items-center justify-center font-black text-white text-[10px]">
            ⚡
          </div>
          <span className="text-xs font-bold tracking-tight text-zinc-200">
            ClipForge AI
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">v{appVersion}</span>
        </div>

        {/* Backend Connectivity Status Badge */}
        <div
          className="flex items-center gap-2"
          style={{ WebkitAppRegion: 'no-drag' } as any}
        >
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#171722] border border-[#232332] text-[10px]">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isBackendConnected && isDbConnected
                  ? 'bg-emerald-500 shadow-sm shadow-emerald-500'
                  : 'bg-rose-500 animate-pulse'
              }`}
            />
            <span className="text-zinc-400 font-medium">
              {isBackendConnected
                ? isDbConnected
                  ? 'Local Engine Active'
                  : 'Database Reconnecting'
                : 'Connecting Backend...'}
            </span>
          </div>
        </div>

        {/* Window Controls */}
        <div
          className="flex items-center gap-1"
          style={{ WebkitAppRegion: 'no-drag' } as any}
        >
          <button
            onClick={() => window.electronAPI?.minimizeWindow()}
            className="h-6 w-7 flex items-center justify-center hover:bg-[#1f1f2b] rounded text-zinc-400 hover:text-zinc-200 transition"
          >
            <Minus className="w-3 h-3" />
          </button>
          <button
            onClick={() => window.electronAPI?.maximizeWindow()}
            className="h-6 w-7 flex items-center justify-center hover:bg-[#1f1f2b] rounded text-zinc-400 hover:text-zinc-200 transition"
          >
            <Square className="w-2.5 h-2.5" />
          </button>
          <button
            onClick={() => window.electronAPI?.closeWindow()}
            className="h-6 w-7 flex items-center justify-center hover:bg-rose-600 rounded text-zinc-400 hover:text-white transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* 2. Main Body with Persistent Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <aside className="w-60 border-r border-[#1f1f2b] bg-[#121218] flex flex-col justify-between p-3 flex-shrink-0">
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id as NavItem)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#181822]'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-zinc-500'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Bottom Hardware Telemetry (Real-time) */}
          <div className="p-3 bg-[#171722] rounded-xl border border-[#232332] space-y-2.5 text-[11px]">
            <div className="flex items-center justify-between pb-1 border-b border-[#232332]">
              <span className="font-bold text-zinc-300 flex items-center gap-1.5 text-[10px] uppercase tracking-wider">
                <Activity className="w-3 h-3 text-indigo-400" />
                Hardware Status
              </span>
              <span className="text-[10px] text-zinc-500 font-mono">RTX 4060</span>
            </div>

            {/* GPU VRAM */}
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] text-zinc-400">
                <span>VRAM ({vramUsedMb || 0}/{vramTotalMb || 0} MB)</span>
                <span className="font-bold text-zinc-200">{vramPercent || 0}%</span>
              </div>
              <div className="h-1.5 w-full bg-[#20202e] rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full transition-all"
                  style={{ width: `${Math.min(vramPercent || 0, 100)}%` }}
                />
              </div>
            </div>

            {/* CPU & RAM */}
            <div className="grid grid-cols-2 gap-2 text-[10px] pt-1">
              <div>
                <span className="text-zinc-500 block">CPU Load</span>
                <span className="font-semibold text-zinc-300">{cpuPercent || 0}%</span>
              </div>
              <div>
                <span className="text-zinc-500 block">RAM ({ramUsedGb || 0} GB)</span>
                <span className="font-semibold text-zinc-300">{ramPercent || 0}%</span>
              </div>
            </div>

            {/* Disk Storage */}
            <div className="pt-1 border-t border-[#232332] flex items-center justify-between text-[10px] text-zinc-400">
              <span className="flex items-center gap-1">
                <HardDrive className="w-3 h-3 text-zinc-500" /> Storage
              </span>
              <span className="font-medium text-zinc-300">{diskPercent || 0}% Used</span>
            </div>
          </div>
        </aside>

        {/* 3. Main Viewport */}
        <main className="flex-1 overflow-y-auto bg-[#0e0e13] p-8">
          {children}
        </main>
      </div>
    </div>
  );
};
