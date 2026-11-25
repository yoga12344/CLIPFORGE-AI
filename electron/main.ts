import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import * as child_process from 'child_process';
import * as crypto from 'crypto';
import * as http from 'http';

let mainWindow: BrowserWindow | null = null;
let backendProcess: child_process.ChildProcess | null = null;

const BACKEND_PORT = 8000;
const SESSION_TOKEN = crypto.randomUUID();
let isBackendReady = false;

function pollBackendHealth(retries = 25, intervalMs = 600): Promise<boolean> {
  return new Promise((resolve) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get(
        `http://127.0.0.1:${BACKEND_PORT}/api/health`,
        { headers: { 'x-session-token': SESSION_TOKEN } },
        (res) => {
          if (res.statusCode === 200) {
            isBackendReady = true;
            resolve(true);
          } else if (attempts < retries) {
            setTimeout(check, intervalMs);
          } else {
            resolve(false);
          }
        }
      );
      req.on('error', () => {
        if (attempts < retries) {
          setTimeout(check, intervalMs);
        } else {
          resolve(false);
        }
      });
      req.end();
    };
    check();
  });
}

function startBackend() {
  const rootDir = path.resolve(__dirname, '..');
  let pythonExecutable = path.join(rootDir, 'backend', 'venv', 'Scripts', 'python.exe');
  let cwd = path.join(rootDir, 'backend');

  if (app.isPackaged) {
    const packagedExe = path.join(process.resourcesPath, 'backend', 'backend.exe');
    const packagedPy = path.join(process.resourcesPath, 'backend', 'venv', 'Scripts', 'python.exe');
    if (fs.existsSync(packagedExe)) {
      pythonExecutable = packagedExe;
      cwd = path.join(process.resourcesPath, 'backend');
    } else if (fs.existsSync(packagedPy)) {
      pythonExecutable = packagedPy;
      cwd = path.join(process.resourcesPath, 'backend');
    }
  }

  console.log(`[Electron] Starting FastAPI backend via ${pythonExecutable}...`);

  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    CLIPFORGE_SESSION_TOKEN: SESSION_TOKEN,
    CLIPFORGE_PORT: BACKEND_PORT.toString(),
  };

  try {
    backendProcess = child_process.spawn(
      pythonExecutable,
      ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', BACKEND_PORT.toString()],
      {
        cwd,
        env,
        stdio: 'pipe',
      }
    );

    backendProcess.stdout?.on('data', (data) => {
      console.log(`[Backend stdout]: ${data}`);
    });

    backendProcess.stderr?.on('data', (data) => {
      console.error(`[Backend stderr]: ${data}`);
    });

    backendProcess.on('exit', (code) => {
      console.log(`[Backend] Process exited with code ${code}`);
      isBackendReady = false;
    });
  } catch (err) {
    console.error('[Electron] Failed to spawn backend process:', err);
  }
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Electron] Terminating backend process...');
    try {
      if (process.platform === 'win32' && backendProcess.pid) {
        child_process.execSync(`taskkill /pid ${backendProcess.pid} /T /F`);
      } else {
        backendProcess.kill('SIGTERM');
      }
    } catch (e) {
      // Process might already be dead
    }
    backendProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1200,
    minHeight: 760,
    backgroundColor: '#0e0e13',
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#0e0e13',
      symbolColor: '#a1a1aa',
      height: 38,
    },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  const distHtmlPath = path.join(__dirname, '../dist/index.html');
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else if (require('fs').existsSync(distHtmlPath)) {
    mainWindow.loadFile(distHtmlPath);
  } else {
    mainWindow.loadURL('http://localhost:5173');
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
ipcMain.handle('app:get-version', () => app.getVersion());

ipcMain.handle('dialog:open-video', async () => {
  if (!mainWindow) return { canceled: true, filePaths: [] };
  return dialog.showOpenDialog(mainWindow, {
    title: 'Select Video File',
    properties: ['openFile'],
    filters: [
      { name: 'Video Files', extensions: ['mp4', 'mov', 'mkv', 'webm', 'avi'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });
});

ipcMain.handle('dialog:open-folder', async () => {
  if (!mainWindow) return { canceled: true, filePaths: [] };
  return dialog.showOpenDialog(mainWindow, {
    title: 'Select Export Folder',
    properties: ['openDirectory', 'createDirectory'],
  });
});

ipcMain.handle('backend:get-session', () => ({
  port: BACKEND_PORT,
  token: SESSION_TOKEN,
  isReady: isBackendReady,
}));

ipcMain.handle('shell:open-path', async (_, targetPath: string) => {
  return shell.openPath(targetPath);
});

ipcMain.handle('shell:show-item-in-folder', async (_, targetPath: string) => {
  shell.showItemInFolder(targetPath);
  return true;
});

ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});
ipcMain.on('window:close', () => mainWindow?.close());

// Lifecycle
app.whenReady().then(async () => {
  // Check if backend is already listening
  const alreadyHealthy = await pollBackendHealth(2, 200);
  if (!alreadyHealthy) {
    startBackend();
  } else {
    console.log('[Electron] Connected to existing active backend process.');
  }

  createWindow();

  const healthy = await pollBackendHealth(30, 500);
  if (healthy) {
    console.log('[Electron] Backend confirmed healthy and operational.');
    mainWindow?.webContents.send('backend:status', { ready: true });
  } else {
    console.warn('[Electron] Backend health check timed out or failed.');
    mainWindow?.webContents.send('backend:status', { ready: false, error: 'Backend initialization timeout' });
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});
