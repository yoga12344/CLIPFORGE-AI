# ClipForge AI — Windows 11 Desktop Release & Packaging Guide
**Version:** 1.0.0-GA  
**Target OS:** Microsoft Windows 11 (64-bit) / Windows 10 (64-bit)  
**Date:** November 23, 2026  

---

## 1. Distribution Artifacts

ClipForge AI produces two production packaging formats via `electron-builder`:
1. **Windows Installer (NSIS):** `release/ClipForge AI Setup 1.0.0.exe`
   * Installs to `%LOCALAPPDATA%\Programs\clipforge-ai`
   * Configures desktop icon, Start Menu shortcut, and uninstaller.
   * Prompts user for installation directory option.
2. **Portable Executable:** `release/ClipForge AI 1.0.0.exe` (or unpacked `release/win-unpacked/`)
   * Self-contained, zero-install portable folder.
   * Useful for USB drives and workstations without administrative permissions.

---

## 2. Prerequisites on Target Machine

* **Operating System:** Windows 10/11 64-bit.
* **FFmpeg / FFprobe:** FFmpeg 6.0+ must be present on system `PATH` or bundled in `resources/ffmpeg/`.
* **Graphics Driver:** NVIDIA Game Ready / Studio Driver 535+ for NVENC hardware acceleration (optional; CPU encoding works out of the box).
* **Python Runtime:** Python 3.11.x embedded runtime included in packaged extra resources.

---

## 3. Build & Packaging Instructions

To package the Windows desktop application from source:

```powershell
# 1. Compile Vite React frontend and Electron main process
npm run compile

# 2. Package desktop executable and installer
npm run build
```

The resulting executables will be generated in `release/`.

---

## 4. First-Time Launch & Verification

1. Double-click `ClipForge AI.exe`.
2. The Electron main process launches and spawns the local FastAPI engine (`127.0.0.1:8000`) with a cryptographically secure session token.
3. The custom titlebar indicates: `Local Engine Active` with a green indicator.
4. Navigate to the **Diagnostics** screen (`Diagnostics & Telemetry`) to verify that GPU VRAM, CPU cores, SQLite WAL mode, and FFmpeg encoders are recognized.
5. In **AI Models**, verify the status of faster-whisper and vision models.
6. In **Import Video**, choose any 16:9 MP4 recording to begin automatic 9:16 portrait clipping!
