"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  Upload,
  Link as LinkIcon,
  Play,
  Pause,
  Download,
  Flame,
  Clock,
  Scissors,
  Wand2,
  FolderKanban,
  LayoutGrid,
  Calendar,
  Palette,
  CreditCard,
  Settings,
  ChevronDown,
  Search,
  CheckCircle2,
  Share2,
  RotateCcw,
  Volume2,
  Maximize2,
  Copy,
  SlidersHorizontal,
  Youtube,
  Film
} from "lucide-react";
import CompositionStudio from "../features/composition/CompositionStudio";

interface Clip {
  id: string;
  title: string;
  hook: string;
  score: number;
  reason: string;
  start: number;
  end: number;
  duration: number;
  video_url: string;
  thumbnail_url?: string;
  transcript: string;
}

interface Job {
  id: string;
  status: string;
  progress: number;
  step_description: string;
  error?: string;
  video_title?: string;
  video_duration?: number;
  clips: Clip[];
  created_at?: string;
}

const BACKEND_URL = "http://localhost:8000";

export default function OpusDashboard() {
  // Navigation
  const [activeNav, setActiveNav] = useState<"home" | "studio" | "projects" | "templates" | "scheduler">("home");

  // Ingestion inputs
  const [inputTab, setInputTab] = useState<"link" | "upload">("link");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);

  // Settings
  const [durationPref, setDurationPref] = useState<string>("30-60");
  const [captionStyle, setCaptionStyle] = useState<string>("karaoke_yellow");
  const [aiProvider, setAiProvider] = useState<string>("auto");
  const [autoReframing, setAutoReframing] = useState<boolean>(true);
  const [maxClips, setMaxClips] = useState<number>(3);

  // Job & UI States
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [selectedClip, setSelectedClip] = useState<Clip | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedClipId, setCopiedClipId] = useState<string | null>(null);

  // Video player controls
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);

  // Fetch recent jobs
  const fetchRecentJobs = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/jobs`);
      if (res.ok) {
        const data = await res.json();
        setRecentJobs(data);
      }
    } catch (e) {
      console.warn("Could not load recent jobs:", e);
    }
  };

  useEffect(() => {
    fetchRecentJobs();
  }, []);

  // Poll current job
  useEffect(() => {
    if (!currentJob || currentJob.status === "completed" || currentJob.status === "failed") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/jobs/${currentJob.id}`);
        if (res.ok) {
          const data: Job = await res.json();
          setCurrentJob(data);
          if (data.status === "completed") {
            fetchRecentJobs();
            if (data.clips.length > 0) {
              setSelectedClip(data.clips[0]);
            }
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentJob]);

  // Handle Video Submit
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);

    let minD = 25;
    let maxD = 60;
    if (durationPref === "<30") { minD = 15; maxD = 30; }
    else if (durationPref === "60-90") { minD = 60; maxD = 90; }

    try {
      let res: Response;
      if (inputTab === "link") {
        if (!url.trim()) throw new Error("Please paste a valid video URL");
        res = await fetch(`${BACKEND_URL}/api/jobs/url`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: url.trim(),
            max_clips: maxClips,
            target_duration_min: minD,
            target_duration_max: maxD,
            ai_provider: aiProvider,
            subtitle_style: captionStyle,
            enable_face_tracking: autoReframing,
          }),
        });
      } else {
        if (!file) throw new Error("Please choose a video file to upload");
        const formData = new FormData();
        formData.append("file", file);
        formData.append("max_clips", maxClips.toString());
        formData.append("target_duration_min", minD.toString());
        formData.append("target_duration_max", maxD.toString());
        formData.append("ai_provider", aiProvider);
        formData.append("subtitle_style", captionStyle);
        formData.append("enable_face_tracking", autoReframing.toString());

        res = await fetch(`${BACKEND_URL}/api/jobs/upload`, {
          method: "POST",
          body: formData,
        });
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to start generation job");
      }

      const jobData = await res.json();
      setCurrentJob(jobData);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit video");
    } finally {
      setIsSubmitting(false);
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const copyTranscript = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedClipId(id);
    setTimeout(() => setCopiedClipId(null), 2000);
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    if (score >= 80) return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    return "text-purple-400 bg-purple-500/10 border-purple-500/30";
  };

  if (activeNav === "studio") {
    return <CompositionStudio onClose={() => setActiveNav("home")} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0a0d] text-zinc-100">
      {/* 1. LEFT SIDEBAR (Opus Clip Style) */}
      <aside className="w-64 border-r border-[#1f1f28] bg-[#0e0e14] flex flex-col justify-between p-4 flex-shrink-0 z-20">
        <div className="space-y-6">
          {/* Logo & Brand */}
          <div className="flex items-center gap-2.5 px-2 py-1">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-purple-600 via-pink-500 to-amber-400 flex items-center justify-center shadow-lg shadow-purple-600/20 font-black text-white text-lg">
              ⚡
            </div>
            <div>
              <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
                Opus Clip
              </span>
              <span className="ml-1.5 px-1.5 py-0.5 text-[9px] font-bold bg-purple-500/20 text-purple-300 rounded border border-purple-500/30">
                PRO
              </span>
            </div>
          </div>

          {/* Nav Items */}
          <nav className="space-y-1">
            {[
              { id: "home", label: "Dashboard", icon: LayoutGrid },
              { id: "studio", label: "Composition Studio", icon: Film },
              { id: "projects", label: "My Projects", icon: FolderKanban },
              { id: "templates", label: "Brand Templates", icon: Palette },
              { id: "scheduler", label: "Social Scheduler", icon: Calendar },
            ].map((item) => {
              const Icon = item.icon;
              const active = activeNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveNav(item.id as any)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                    active
                      ? "bg-purple-600/15 text-purple-400 border border-purple-500/30 font-bold"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                  }`}
                >
                  <Icon className={`w-4 h-4 ${active ? "text-purple-400" : "text-zinc-400"}`} />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom Credits & Account Card */}
        <div className="space-y-3">
          <div className="p-3.5 bg-[#14141d] rounded-2xl border border-[#232332] space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
                <Flame className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                Credits Remaining
              </span>
              <span className="font-bold text-white">94 / 120m</span>
            </div>
            <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
              <div className="bg-gradient-to-r from-purple-500 to-amber-400 h-full w-[78%] rounded-full" />
            </div>
            <p className="text-[11px] text-zinc-400">Resets in 12 days</p>
          </div>

          <div className="flex items-center justify-between px-2 pt-1 border-t border-[#1f1f28] text-xs text-zinc-400">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center font-bold text-white text-[11px]">
                JD
              </div>
              <span className="font-medium text-zinc-200 truncate max-w-[100px]">Creator Team</span>
            </div>
            <Settings className="w-4 h-4 hover:text-zinc-200 cursor-pointer" />
          </div>
        </div>
      </aside>

      {/* 2. MAIN WORKSPACE CANVAS */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Navbar */}
        <header className="h-16 border-b border-[#1f1f28] bg-[#0e0e14]/80 backdrop-blur px-8 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#14141d] border border-[#232332] rounded-xl text-xs font-semibold cursor-pointer hover:border-zinc-600">
              <span>Personal Workspace</span>
              <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
            </div>

            <div className="relative hidden md:block">
              <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search projects or clips..."
                className="bg-[#14141d] border border-[#232332] rounded-xl pl-9 pr-4 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-purple-500 w-64"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                const el = document.getElementById("clip-input-box");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-purple-600/20 flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Get Clips in 1 Click
            </button>
          </div>
        </header>

        {/* Scrollable Content Body */}
        <main className="flex-1 overflow-y-auto px-8 py-8 space-y-10">
          {/* HERO INGESTION CARD (Opus Clip Style) */}
          <section id="clip-input-box" className="max-w-4xl mx-auto space-y-4">
            <div className="text-center space-y-2 mb-6">
              <h1 className="text-3xl font-extrabold text-white tracking-tight">
                Turn 1 Long Video into <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-amber-300 bg-clip-text text-transparent">10 Viral Shorts</span>
              </h1>
              <p className="text-zinc-400 text-sm">
                AI extracts hooks, reframes speakers to 9:16 with face tracking, and burns in animated karaoke captions.
              </p>
            </div>

            <div className="bg-[#12121a] border border-[#232332] rounded-2xl p-6 shadow-2xl relative overflow-hidden space-y-5">
              {/* Glowing decorative glow */}
              <div className="absolute top-0 right-10 w-72 h-72 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />

              {/* Input Switcher (Link vs Upload) */}
              <div className="flex items-center justify-between border-b border-[#232332] pb-4">
                <div className="flex items-center gap-2 bg-[#181824] p-1 rounded-xl">
                  <button
                    type="button"
                    onClick={() => setInputTab("link")}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                      inputTab === "link"
                        ? "bg-purple-600 text-white shadow"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <LinkIcon className="w-3.5 h-3.5" />
                    Drop a Link
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputTab("upload")}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                      inputTab === "upload"
                        ? "bg-purple-600 text-white shadow"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <Upload className="w-3.5 h-3.5" />
                    Upload File
                  </button>
                </div>

                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <span className="flex items-center gap-1 font-medium text-zinc-400">
                    <Youtube className="w-4 h-4 text-red-500" /> YouTube
                  </span>
                  <span>•</span>
                  <span>Google Drive</span>
                  <span>•</span>
                  <span>Zoom</span>
                </div>
              </div>

              {/* Form Input */}
              <form onSubmit={handleGenerate} className="space-y-5">
                {inputTab === "link" ? (
                  <div className="relative">
                    <input
                      type="url"
                      placeholder="Paste your YouTube link, Zoom, or video URL..."
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      className="w-full bg-[#181824] border border-[#29293d] focus:border-purple-500 rounded-xl px-4 py-3.5 text-sm text-white placeholder-zinc-500 focus:outline-none transition-all pr-24"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          const text = await navigator.clipboard.readText();
                          setUrl(text);
                        } catch (e) {}
                      }}
                      className="absolute right-2.5 top-2.5 px-3 py-1.5 bg-[#252538] hover:bg-[#2d2d44] text-xs font-semibold rounded-lg text-zinc-300 transition-all cursor-pointer"
                    >
                      Paste Link
                    </button>
                  </div>
                ) : (
                  <div className="border-2 border-dashed border-[#29293d] hover:border-purple-500 rounded-xl p-8 text-center transition-all bg-[#181824]/40 cursor-pointer relative">
                    <input
                      type="file"
                      accept="video/*"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                      className="absolute inset-0 opacity-0 cursor-pointer"
                    />
                    <div className="flex flex-col items-center gap-2">
                      <Upload className="w-7 h-7 text-purple-400" />
                      <p className="text-sm font-semibold text-zinc-200">
                        {file ? file.name : "Choose a local video file (MP4, MOV, MKV)"}
                      </p>
                      <p className="text-xs text-zinc-500">Up to 2GB or 2 hours long</p>
                    </div>
                  </div>
                )}

                {/* Opus Preset Controls */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-1">
                  {/* Preferred Clip Length */}
                  <div className="bg-[#181824] p-3 rounded-xl border border-[#29293d] space-y-1.5">
                    <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block">
                      Clip Length
                    </span>
                    <div className="grid grid-cols-3 gap-1">
                      {["<30", "30-60", "60-90"].map((d) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setDurationPref(d)}
                          className={`py-1 text-[11px] font-bold rounded-lg transition-all ${
                            durationPref === d
                              ? "bg-purple-600 text-white"
                              : "bg-[#252538] text-zinc-400 hover:text-zinc-200"
                          }`}
                        >
                          {d}s
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Caption Preset */}
                  <div className="bg-[#181824] p-3 rounded-xl border border-[#29293d] space-y-1.5">
                    <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block">
                      Caption Style
                    </span>
                    <select
                      value={captionStyle}
                      onChange={(e) => setCaptionStyle(e.target.value)}
                      className="w-full bg-[#252538] border border-[#323249] text-xs rounded-lg px-2 py-1.5 text-zinc-200 focus:outline-none"
                    >
                      <option value="karaoke_yellow">🔥 Opus Yellow Pop</option>
                      <option value="karaoke_green">⚡ Beast Neon Green</option>
                      <option value="minimal_white">✨ Minimalist White</option>
                    </select>
                  </div>

                  {/* AI Model */}
                  <div className="bg-[#181824] p-3 rounded-xl border border-[#29293d] space-y-1.5">
                    <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block">
                      AI Hook Model
                    </span>
                    <select
                      value={aiProvider}
                      onChange={(e) => setAiProvider(e.target.value)}
                      className="w-full bg-[#252538] border border-[#323249] text-xs rounded-lg px-2 py-1.5 text-zinc-200 focus:outline-none"
                    >
                      <option value="auto">Auto (Smart Detect)</option>
                      <option value="claude">Claude 3.5 Sonnet</option>
                      <option value="gemini">Gemini 2.5 Flash</option>
                      <option value="openai">OpenAI GPT-4o</option>
                    </select>
                  </div>

                  {/* Auto Reframing */}
                  <div className="bg-[#181824] p-3 rounded-xl border border-[#29293d] flex flex-col justify-between">
                    <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block">
                      Auto Reframing
                    </span>
                    <label className="flex items-center gap-2 cursor-pointer select-none pb-0.5">
                      <input
                        type="checkbox"
                        checked={autoReframing}
                        onChange={(e) => setAutoReframing(e.target.checked)}
                        className="rounded border-zinc-700 text-purple-600 focus:ring-0"
                      />
                      <span className="text-xs font-semibold text-zinc-300">Face Tracking (9:16)</span>
                    </label>
                  </div>
                </div>

                {errorMsg && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
                    {errorMsg}
                  </div>
                )}

                {/* Big Action Button */}
                <button
                  type="submit"
                  disabled={Boolean(isSubmitting || (currentJob && currentJob.status !== "completed" && currentJob.status !== "failed"))}
                  className="w-full py-4 bg-gradient-to-r from-purple-600 via-pink-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-extrabold rounded-xl shadow-xl shadow-purple-600/30 flex items-center justify-center gap-2 text-base transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  <Wand2 className="w-5 h-5" />
                  {isSubmitting ? "Submitting Pipeline..." : "Get Clips in 1 Click"}
                </button>
              </form>
            </div>
          </section>

          {/* ACTIVE PIPELINE MONITOR (During Generation) */}
          {currentJob && currentJob.status !== "completed" && (
            <section className="max-w-4xl mx-auto bg-[#12121a] border border-[#232332] rounded-2xl p-6 shadow-xl space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-purple-400 uppercase tracking-wider">
                    Opus Pipeline Engine
                  </span>
                  <h3 className="text-lg font-bold text-white">
                    {currentJob.status === "failed" ? "Processing Failed" : "Processing Your Video..."}
                  </h3>
                </div>
                <span className="text-2xl font-black text-white">{currentJob.progress}%</span>
              </div>

              <div className="w-full bg-[#181824] h-2.5 rounded-full overflow-hidden border border-[#29293d]">
                <div
                  className="bg-gradient-to-r from-purple-500 via-pink-500 to-amber-400 h-full transition-all duration-500 rounded-full"
                  style={{ width: `${currentJob.progress}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-purple-500 animate-ping" />
                  {currentJob.step_description}
                </span>
                <span>Auto-framing active</span>
              </div>
            </section>
          )}

          {/* GENERATED RESULTS STUDIO (Opus Clip Showcase) */}
          {currentJob && currentJob.clips.length > 0 && (
            <section className="max-w-6xl mx-auto space-y-6">
              <div className="flex items-center justify-between border-b border-[#1f1f28] pb-4">
                <div>
                  <h2 className="text-2xl font-extrabold text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-amber-400" />
                    Generated Clips ({currentJob.clips.length})
                  </h2>
                  <p className="text-zinc-400 text-xs">
                    Ranked by AI virality score. Pick any clip to preview or export in 1080p.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                {/* Left 4 Cols: Clip Cards List */}
                <div className="lg:col-span-5 space-y-3.5">
                  {currentJob.clips.map((clip, index) => {
                    const isSelected = selectedClip?.id === clip.id;
                    const scoreStyle = getScoreColor(clip.score);
                    return (
                      <div
                        key={clip.id}
                        onClick={() => setSelectedClip(clip)}
                        className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                          isSelected
                            ? "bg-[#161622] border-purple-500 shadow-xl shadow-purple-500/10"
                            : "bg-[#12121a] border-[#232332] hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1.5 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-[#1f1f2e] text-zinc-300">
                                Clip #{index + 1}
                              </span>
                              <span className={`text-[11px] font-extrabold px-2 py-0.5 rounded-md border flex items-center gap-1 ${scoreStyle}`}>
                                <Flame className="w-3 h-3 fill-current" />
                                {clip.score}/100
                              </span>
                              <span className="text-[11px] text-zinc-500 font-medium">
                                {clip.duration}s
                              </span>
                            </div>
                            <h4 className="font-extrabold text-sm text-white line-clamp-1">
                              {clip.title}
                            </h4>
                          </div>
                        </div>

                        <p className="text-xs text-zinc-400 mt-2 line-clamp-2 italic">
                          "{clip.hook}"
                        </p>

                        <div className="flex items-center justify-between text-[11px] text-zinc-500 mt-3 pt-2.5 border-t border-[#1f1f2e]">
                          <span>
                            {clip.start.toFixed(1)}s - {clip.end.toFixed(1)}s
                          </span>
                          <span className="text-purple-400 font-semibold">9:16 Reframed</span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Right 7 Cols: Active Clip Studio & Video Player */}
                {selectedClip && (
                  <div className="lg:col-span-7 bg-[#12121a] border border-[#232332] rounded-2xl p-6 space-y-6">
                    <div className="flex flex-col md:flex-row gap-6">
                      {/* Vertical 9:16 Video Player */}
                      <div className="w-full md:w-60 flex-shrink-0 bg-black rounded-2xl overflow-hidden shadow-2xl border border-[#232332] relative group flex flex-col justify-center">
                        <video
                          ref={videoRef}
                          key={selectedClip.video_url}
                          src={`${BACKEND_URL}${selectedClip.video_url}`}
                          className="w-full aspect-[9/16] object-cover"
                          loop
                          playsInline
                          onTimeUpdate={() => {
                            if (videoRef.current) {
                              setCurrentTime(videoRef.current.currentTime);
                              setVideoDuration(videoRef.current.duration || selectedClip.duration);
                            }
                          }}
                        />

                        {/* Video Controls Overlay */}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-3">
                          <div className="flex items-center justify-between">
                            <button
                              onClick={togglePlay}
                              className="p-2 rounded-full bg-white/20 hover:bg-white/40 text-white transition cursor-pointer"
                            >
                              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
                            </button>
                            <span className="text-[11px] text-white font-mono">
                              {currentTime.toFixed(1)}s / {selectedClip.duration}s
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Clip Details, Hook Breakdown & Actions */}
                      <div className="flex-1 space-y-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className={`text-xs font-extrabold px-2.5 py-1 rounded-full border flex items-center gap-1 ${getScoreColor(selectedClip.score)}`}>
                              <Flame className="w-3.5 h-3.5 fill-current" />
                              Virality Score: {selectedClip.score}/100
                            </span>
                            <span className="text-xs text-zinc-400 font-semibold">
                              {selectedClip.duration}s Vertical Short
                            </span>
                          </div>
                          <h3 className="text-xl font-extrabold text-white">
                            {selectedClip.title}
                          </h3>
                        </div>

                        {/* Virality Reason */}
                        <div className="bg-[#181824] p-3.5 rounded-xl border border-[#29293d] space-y-1">
                          <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider block">
                            AI Virality Analysis
                          </span>
                          <p className="text-xs text-zinc-300 leading-relaxed">
                            {selectedClip.reason || "Strong opening question that creates an immediate curiosity gap, driving 80%+ audience retention."}
                          </p>
                        </div>

                        {/* Hook */}
                        <div className="bg-[#181824] p-3.5 rounded-xl border border-[#29293d] space-y-1">
                          <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider block">
                            Opening Hook
                          </span>
                          <p className="text-xs text-zinc-200 italic font-medium">
                            "{selectedClip.hook}"
                          </p>
                        </div>

                        {/* Transcript Preview */}
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between text-xs text-zinc-400">
                            <span className="font-semibold text-zinc-300">Word-by-word Transcript:</span>
                            <button
                              onClick={() => copyTranscript(selectedClip.transcript, selectedClip.id)}
                              className="flex items-center gap-1 text-[11px] text-purple-400 hover:text-purple-300 transition cursor-pointer"
                            >
                              <Copy className="w-3 h-3" />
                              {copiedClipId === selectedClip.id ? "Copied!" : "Copy"}
                            </button>
                          </div>
                          <div className="bg-[#181824] p-3 rounded-xl border border-[#29293d] text-xs text-zinc-300 max-h-32 overflow-y-auto leading-relaxed font-normal">
                            {selectedClip.transcript}
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="pt-2 flex items-center gap-3">
                          <button
                            onClick={() => setActiveNav("studio")}
                            className="py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-extrabold rounded-xl flex items-center justify-center gap-2 text-xs shadow-lg shadow-indigo-600/30 transition cursor-pointer"
                          >
                            <SlidersHorizontal className="w-4 h-4" />
                            Edit in Studio
                          </button>
                          <a
                            href={`${BACKEND_URL}${selectedClip.video_url}`}
                            download={`${selectedClip.id}.mp4`}
                            className="flex-1 py-3 px-4 bg-purple-600 hover:bg-purple-500 text-white font-extrabold rounded-xl flex items-center justify-center gap-2 text-xs shadow-lg shadow-purple-600/30 transition cursor-pointer"
                          >
                            <Download className="w-4 h-4" />
                            Download 1080p Short
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* RECENT PROJECTS SECTION */}
          {recentJobs.length > 0 && (
            <section className="max-w-6xl mx-auto space-y-4 pt-4 border-t border-[#1f1f28]">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Film className="w-4 h-4 text-purple-400" />
                  Recent Projects ({recentJobs.length})
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {recentJobs.map((job) => (
                  <div
                    key={job.id}
                    onClick={() => {
                      setCurrentJob(job);
                      if (job.clips.length > 0) setSelectedClip(job.clips[0]);
                    }}
                    className="p-4 bg-[#12121a] border border-[#232332] hover:border-purple-500/50 rounded-2xl cursor-pointer transition space-y-2"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-zinc-300 truncate max-w-[180px]">
                        {job.video_title || `Project #${job.id}`}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        job.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-purple-500/10 text-purple-400"
                      }`}>
                        {job.status}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-500">
                      {job.clips.length} viral clips generated • {job.video_duration ? `${job.video_duration.toFixed(0)}s source` : "Processed"}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
