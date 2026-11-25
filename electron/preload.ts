import { contextBridge, ipcRenderer } from 'electron';

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

const electronAPI: ElectronAPI = {
  platform: process.platform,
  getVersion: () => ipcRenderer.invoke('app:get-version'),
  openVideoDialog: () => ipcRenderer.invoke('dialog:open-video'),
  openFolderDialog: () => ipcRenderer.invoke('dialog:open-folder'),
  getBackendSession: () => ipcRenderer.invoke('backend:get-session'),
  openPath: (filePath: string) => ipcRenderer.invoke('shell:open-path', filePath),
  showItemInFolder: (filePath: string) => ipcRenderer.invoke('shell:show-item-in-folder', filePath),
  minimizeWindow: () => ipcRenderer.send('window:minimize'),
  maximizeWindow: () => ipcRenderer.send('window:maximize'),
  closeWindow: () => ipcRenderer.send('window:close'),
};

contextBridge.exposeInMainWorld('electronAPI', electronAPI);
