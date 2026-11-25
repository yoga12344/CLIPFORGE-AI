export interface ElectronAPI {
  platform: string;
  getVersion: () => Promise<string>;
  openVideoDialog: () => Promise<{ canceled: boolean; filePaths: string[] }>;
  openFolderDialog: () => Promise<{ canceled: boolean; filePaths: string[] }>;
  getBackendSession: () => Promise<{ port: number; token: string; isReady: boolean }>;
  openPath: (filePath: string) => Promise<string>;
  showItemInFolder: (filePath: string) => Promise<boolean>;
  minimizeWindow: () => void;
  maximizeWindow: () => void;
  closeWindow: () => void;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
