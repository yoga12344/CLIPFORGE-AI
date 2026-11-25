import { create } from 'zustand';
import { api } from '../services/api';

interface SystemState {
  isBackendConnected: boolean;
  isDbConnected: boolean;
  appVersion: string;
  storageDir: string;
  cpuPercent: number;
  cpuCores: number;
  ramUsedGb: number;
  ramTotalGb: number;
  ramPercent: number;
  diskUsedGb: number;
  diskTotalGb: number;
  diskPercent: number;
  gpuName: string;
  hasGpu: boolean;
  vramUsedMb: number;
  vramTotalMb: number;
  vramPercent: number;
  gpuUtilPercent: number | null;
  gpuTemp: number | null;
  nvencAvailable: boolean;
  ffmpegPath: string;
  lastChecked: Date | null;
  fetchStatus: () => Promise<void>;
}

export const useSystemStore = create<SystemState>((set) => ({
  isBackendConnected: false,
  isDbConnected: false,
  appVersion: '1.0.0',
  storageDir: '',
  cpuPercent: 0,
  cpuCores: 0,
  ramUsedGb: 0,
  ramTotalGb: 0,
  ramPercent: 0,
  diskUsedGb: 0,
  diskTotalGb: 0,
  diskPercent: 0,
  gpuName: 'Checking...',
  hasGpu: false,
  vramUsedMb: 0,
  vramTotalMb: 0,
  vramPercent: 0,
  gpuUtilPercent: null,
  gpuTemp: null,
  nvencAvailable: false,
  ffmpegPath: '',
  lastChecked: null,

  fetchStatus: async () => {
    try {
      const health = await api.getHealth();
      const status = await api.getSystemStatus();

      set({
        isBackendConnected: health.status === 'online',
        isDbConnected: health.database_connected,
        appVersion: health.version,
        storageDir: health.storage_dir,
        ffmpegPath: health.ffmpeg,
        cpuPercent: status.cpu.utilization_percent,
        cpuCores: status.cpu.cores_logical,
        ramUsedGb: status.ram.used_gb,
        ramTotalGb: status.ram.total_gb,
        ramPercent: status.ram.percent,
        diskUsedGb: status.disk.used_gb,
        diskTotalGb: status.disk.total_gb,
        diskPercent: status.disk.percent,
        gpuName: status.gpu.gpu_name,
        hasGpu: status.gpu.has_gpu,
        vramUsedMb: status.gpu.vram_used_mb,
        vramTotalMb: status.gpu.vram_total_mb,
        vramPercent: status.gpu.vram_percent,
        gpuUtilPercent: status.gpu.utilization_gpu_percent,
        gpuTemp: status.gpu.temperature_c,
        nvencAvailable: status.gpu.nvenc_available,
        lastChecked: new Date(),
      });
    } catch (err) {
      set({
        isBackendConnected: false,
        isDbConnected: false,
        lastChecked: new Date(),
      });
    }
  },
}));
