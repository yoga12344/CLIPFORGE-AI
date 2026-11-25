# ClipsMaster ⚡
> **OpusClip-Style AI Long Video to Viral Shorts Pipeline**

Turn long-form videos into high-retention 9:16 vertical shorts (TikTok, Reels, YouTube Shorts) with AI-powered hook selection, dynamic face tracking, and animated karaoke captions.

---

## 🚀 Key Features

* **Dual Input Flow**: Direct video file uploads (.mp4, .mov, .mkv) or YouTube links via `yt-dlp`.
* **Word-Level Transcription**: Faster-Whisper integration with exact word timestamps (`start`, `end`, `probability`).
* **Multi-LLM Highlight Intelligence**: Prompt-engineered virality scoring (60–99), hook identification, and clean narrative boundaries using:
  * Anthropic Claude (`claude-3-5-sonnet`)
  * Google Gemini (`gemini-2.5-flash`)
  * OpenAI (`gpt-4o`)
  * Smart Heuristic Fallback (works offline without API keys for testing)
* **Smart Face Tracking & Auto-Framing**: MediaPipe and OpenCV face detection with Exponential Moving Average (EMA) smoothing to re-center speakers into vertical 9:16 without camera jitter.
* **Animated Karaoke Subtitles**: Advanced SubStation Alpha (`.ass`) generator with word-by-word active pop highlights (Neon Yellow, Electric Green, Minimal White).
* **Broadcast-Grade FFmpeg Processing**: Hardware-accelerated cropping, libass subtitle burn-in, `-14 LUFS` EBU R128 audio normalization, and `+faststart` web-ready MP4 encoding.
* **Modern Creator Studio UI**: Built with Next.js 14, Tailwind CSS, Lucide icons, live pipeline progress tracking, and interactive 9:16 video playback.

---

## 🛠️ Project Structure

```text
clipsmaster/
├── backend/
│   ├── app/
│   │   ├── api/routes.py            # FastAPI endpoints (submit jobs, stream status, list clips)
│   │   ├── services/
│   │   │   ├── downloader.py        # yt-dlp & file storage probe
│   │   │   ├── transcriber.py       # faster-whisper word-level extractor
│   │   │   ├── highlight_engine.py  # Claude / Gemini / OpenAI hook detector
│   │   │   ├── face_tracker.py      # MediaPipe / OpenCV face centering
│   │   │   ├── subtitles.py         # Word-level .ass karaoke builder
│   │   │   └── video_processor.py   # FFmpeg trimming, cropping & burn-in
│   │   ├── models/schemas.py        # Pydantic data schemas
│   │   ├── config.py                # Environment & FFmpeg auto-detection
│   │   └── main.py                  # Server entrypoint with static mounts
│   ├── .env                         # API keys & model configuration
│   └── requirements.txt
├── frontend/                        # Next.js 14 App Router studio
│   ├── src/app/page.tsx             # Studio dashboard & 9:16 player
│   └── package.json
├── run_backend.bat                  # One-click FastAPI launcher
├── run_frontend.bat                 # One-click Next.js launcher
└── run_demo.py                      # Verification test script
```

---

## ⚡ Quick Start

### 1. Test the Core Pipeline
You can run an end-to-end synthetic video generation test right now:
```bash
.\backend\venv\Scripts\python.exe run_demo.py
```
This will generate a test video, build the `.ass` karaoke subtitles, crop to 9:16, burn in the subtitles, and output `demo_output_clip.mp4` in `backend/storage/outputs/`.

### 2. Start the Backend API (FastAPI)
Double-click `run_backend.bat` or run:
```bash
.\backend\venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be live at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Start the Frontend Studio (Next.js)
Double-click `run_frontend.bat` or run:
```bash
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🔑 Environment Configuration
Edit `backend/.env` to configure your API keys:
```env
FFMPEG_PATH=C:\Users\yogac\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
ANTHROPIC_API_KEY=your_claude_api_key
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
```
*(Note: If no API key is provided, the engine automatically uses its intelligent heuristic extractor so you can test immediately.)*
