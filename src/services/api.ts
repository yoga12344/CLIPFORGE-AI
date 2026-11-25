const API_BASE_URL = 'http://127.0.0.1:8000/api';

export interface ProjectData {
  id: string;
  name: string;
  description: string | null;
  status: string;
  video_count: number;
  clip_count: number;
  created_at: string;
  updated_at: string;
}

export interface DashboardStatsData {
  total_projects: number;
  total_videos: number;
  total_clips: number;
  total_exports: number;
  active_jobs: number;
  recent_projects: ProjectData[];
}

export interface VideoProbeData {
  valid: boolean;
  error?: string;
  filename: string;
  file_path: string;
  file_size_bytes: number;
  format_name?: string;
  duration_seconds: number;
  width: number;
  height: number;
  fps: number;
  video_codec?: string;
  audio_codec?: string;
  has_audio: boolean;
  audio_channels: number;
}

export interface VideoData {
  id: string;
  project_id: string;
  filename: string;
  file_path: string;
  file_size_bytes: number;
  format?: string;
  duration_seconds: number;
  width: number;
  height: number;
  fps: number;
  video_codec?: string;
  audio_codec?: string;
  has_audio: boolean;
  thumbnail_path?: string;
  preview_path?: string;
  created_at: string;
}

export interface VideoCapabilitiesData {
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  ffmpeg_path: string;
  ffprobe_path: string;
  ffmpeg_version: string;
  ffprobe_version: string;
  h264_nvenc_available: boolean;
  hevc_nvenc_available: boolean;
  libx264_available: boolean;
  libx265_available: boolean;
  nvenc_functional: boolean;
  libx264_functional: boolean;
  libass_available: boolean;
  subtitle_filter_available: boolean;
  supported_audio_encoders: string[];
  recommended_video_encoder: string;
  diagnostic_notes: string[];
}

export interface LLMModelData {
  id: string;
  name: string;
  parameter_count: string;
  quantization: string;
  file_name: string;
  file_size_bytes: number;
  context_window: number;
  is_default: boolean;
  description: string;
  is_installed: boolean;
  is_downloading: boolean;
  file_path?: string;
}

export interface LLMInferenceStatusData {
  is_busy: boolean;
  active_model_id?: string;
  loaded_at?: number;
  llama_binary_available: boolean;
  installed_models: string[];
}

export interface ScoreBreakdownData {
  overall_score: number;
  hook_strength: number;
  content_value: number;
  narrative_completeness: number;
  standalone_context: number;
  interest_level: number;
  conciseness: number;
  ending_quality: number;
  penalties: string[];
  strengths: string[];
}

export interface HighlightCandidateData {
  id: string;
  project_id: string;
  video_id: string;
  transcript_id?: string;
  clip_id?: string;
  start_time: number;
  end_time: number;
  duration_seconds: number;
  title: string;
  hook?: string;
  summary?: string;
  reason?: string;
  category: string;
  key_quote?: string;
  transcript_excerpt?: string;
  overall_score: number;
  score_breakdown?: ScoreBreakdownData;
  model_name: string;
  generation_method: string;
  status: 'discovered' | 'approved' | 'rejected' | 'edited' | 'ready_for_render';
  created_at: string;
  updated_at: string;
}

export interface NormalizedBBoxData {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TrackedFaceData {
  id: string;
  track_id: string;
  start_time: number;
  end_time: number;
  detection_count: number;
  average_confidence: number;
  average_bbox?: NormalizedBBoxData;
  sample_count: number;
}

export interface ManualCropData {
  id: string;
  timestamp_seconds: number;
  crop_x: number;
  crop_y: number;
  crop_width: number;
  crop_height: number;
}

export interface VisionAnalysisData {
  id: string;
  video_id: string;
  clip_id?: string;
  status: string;
  model_used: string;
  sampling_fps: number;
  total_frames_sampled: number;
  frames_with_faces: number;
  scene_type: string;
  composition_data?: {
    total_frames_sampled: number;
    frames_with_faces: number;
    max_simultaneous_faces: number;
    average_face_count: number;
    primary_track_id?: string;
    has_multiple_subjects: boolean;
    has_no_faces: boolean;
    scene_type: string;
  };
  tracks: TrackedFaceData[];
  manual_crops: ManualCropData[];
}

export interface CropCoordinateData {
  timestamp_seconds: number;
  crop_x: number;
  crop_y: number;
  crop_width: number;
  crop_height: number;
  pixel_x: number;
  pixel_y: number;
  pixel_width: number;
  pixel_height: number;
  selected_track_id?: string;
  confidence: number;
  reframing_mode: string;
}

export interface ReframeConfigData {
  aspect_ratio: string;
  strategy: string;
  selected_track_id?: string;
  smoothing_strength: number;
  crop_padding: number;
  headroom: number;
  max_crop_velocity_per_sec: number;
  face_confidence_threshold: number;
  sampling_fps: number;
}

export interface ReframePresetData {
  id: string;
  name: string;
  aspect_ratio: string;
  strategy: string;
  smoothing_strength: number;
  crop_padding: number;
  headroom: number;
  max_crop_velocity_per_sec: number;
  is_default: boolean;
  created_at: string;
}

export interface SubtitleWordData {
  word: string;
  start: number;
  end: number;
  prob?: number;
  edited?: boolean;
}

export interface SubtitleSegmentData {
  id: string;
  start: number;
  end: number;
  text: string;
  words: SubtitleWordData[];
  speaker_id?: string;
}

export interface CaptionPresetData {
  id?: string;
  name: string;
  font_family: string;
  font_size: number;
  primary_color: string;
  highlight_color: string;
  outline_color: string;
  outline_width: number;
  shadow_width: number;
  bold: boolean;
  italic: boolean;
  alignment: number;
  margin_v: number;
  margin_l: number;
  margin_r: number;
  max_words_per_line: number;
  max_lines: number;
  bg_color: string;
  bg_padding: number;
  animation_style: string;
  is_default: boolean;
}

export interface SubtitleTrackData {
  id: string;
  clip_id: string;
  preset_id?: string;
  language: string;
  is_enabled: boolean;
  style_overrides?: any;
  segments: SubtitleSegmentData[];
  preset?: CaptionPresetData;
}

export interface ExportData {
  id: string;
  clip_id: string;
  preset_id?: string;
  output_path: string;
  resolution: string;
  fps: number;
  bitrate_kbps: number;
  codec: string;
  file_size_bytes?: number;
  duration_seconds: number;
  burn_subtitles: boolean;
  subtitle_settings?: any;
  status: string;
  error_message?: string;
  created_at: string;
}

export interface AnalyzeHighlightsParams {
  model_name?: string;
  content_type?: string;
  target_duration_min?: number;
  target_duration_max?: number;
  max_candidates?: number;
  auto_create_clips?: boolean;
}

export interface ClipData {
  id: string;
  project_id: string;
  video_id: string;
  title: string;
  start_time: number;
  end_time: number;
  duration_seconds: number;
  aspect_ratio: string;
  file_path: string | null;
  thumbnail_path: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface JobData {
  id: string;
  project_id: string | null;
  job_type: string;
  status: string; // queued, running, completed, failed, cancelled
  progress_percent: number;
  stage_description: string;
  error_message: string | null;
  params: Record<string, any> | null;
  result_data: Record<string, any> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TranscriptWord {
  word: string;
  start: number;
  end: number;
  prob: number;
}

export interface TranscriptSegmentData {
  id: string;
  segment_index: number;
  start_time: number;
  end_time: number;
  text: string;
  confidence?: number;
  words?: TranscriptWord[];
}

export interface TranscriptData {
  id: string;
  video_id: string;
  language: string;
  model_used?: string;
  status: string;
  task_type: string;
  device_used?: string;
  processing_duration_seconds?: number;
  full_text: string;
  created_at: string;
  updated_at?: string;
  segments: TranscriptSegmentData[];
}

export interface WhisperModelData {
  model_id: string;
  display_name: string;
  description: string;
  parameter_count: string;
  is_installed: boolean;
  is_downloading: boolean;
  disk_size_mb: number;
  recommended_vram_mb: number;
  license: string;
  source_url: string;
}

export interface InferenceStatusData {
  ctranslate2_version: string;
  faster_whisper_version: string;
  cuda_available: boolean;
  cuda_device_count: number;
  cuda_functional: boolean;
  cpu_supported_compute_types: string[];
  cuda_supported_compute_types: string[];
  recommended_device: string;
  recommended_compute_type: string;
  diagnostic_message?: string;
}

export interface SettingsData {
  theme: string;
  language: string;
  startup_behavior: string;
  project_storage_path: string;
  cache_path: string;
  export_directory: string;
  gpu_acceleration: boolean;
  cpu_fallback: boolean;
  max_concurrent_gpu_jobs: number;
  vram_budget_mb: number;
  default_transcription_model: string;
  default_llm_model: string;
  model_storage_location: string;
  [key: string]: any;
}

class ApiService {
  private sessionToken: string = '';

  constructor() {
    this.initSession();
  }

  async initSession() {
    if (typeof window !== 'undefined' && window.electronAPI?.getBackendSession) {
      try {
        const session = await window.electronAPI.getBackendSession();
        this.sessionToken = session.token;
      } catch (e) {
        console.warn('[API] Could not fetch Electron session token:', e);
      }
    }
  }

  getSessionToken(): string {
    return this.sessionToken;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    if (!this.sessionToken && window.electronAPI?.getBackendSession) {
      await this.initSession();
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.sessionToken) {
      headers['x-session-token'] = this.sessionToken;
    }

    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Request failed with status ${res.status}`);
    }

    if (res.status === 204) {
      return null as any;
    }

    return res.json();
  }

  // Health & System
  async getHealth() {
    return this.request<{
      status: string;
      app: string;
      version: string;
      database_connected: boolean;
      storage_dir: string;
      ffmpeg: string;
    }>('/health');
  }

  async getSystemStatus() {
    return this.request<{
      cpu: {
        utilization_percent: number;
        cores_logical: number;
        cores_physical: number;
      };
      ram: {
        total_gb: number;
        used_gb: number;
        free_gb: number;
        percent: number;
      };
      disk: {
        path: string;
        total_gb: number;
        used_gb: number;
        free_gb: number;
        percent: number;
      };
      gpu: {
        has_gpu: boolean;
        gpu_name: string;
        driver_version: string;
        vram_total_mb: number;
        vram_used_mb: number;
        vram_free_mb: number;
        vram_percent: number;
        temperature_c: number | null;
        utilization_gpu_percent: number | null;
        nvenc_available: boolean;
      };
      ffmpeg: {
        path: string;
        available: boolean;
      };
    }>('/system/status');
  }

  async getVideoCapabilities(forceRefresh: boolean = false) {
    return this.request<VideoCapabilitiesData>(
      `/system/video-capabilities?force_refresh=${forceRefresh}`
    );
  }

  // Dashboard
  async getDashboardStats() {
    return this.request<DashboardStatsData>('/dashboard/stats');
  }

  // Projects CRUD
  async listProjects(search?: string, sortBy: string = 'updated_at', sortOrder: string = 'desc') {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    params.append('sort_by', sortBy);
    params.append('sort_order', sortOrder);
    return this.request<ProjectData[]>(`/projects?${params.toString()}`);
  }

  async createProject(name: string, description?: string) {
    return this.request<ProjectData>('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    });
  }

  async getProject(id: string) {
    return this.request<ProjectData>(`/projects/${id}`);
  }

  async updateProject(id: string, data: { name?: string; description?: string }) {
    return this.request<ProjectData>(`/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteProject(id: string) {
    return this.request<void>(`/projects/${id}`, {
      method: 'DELETE',
    });
  }

  // Videos
  async probeVideo(filePath: string) {
    return this.request<VideoProbeData>('/videos/probe', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath }),
    });
  }

  async importVideo(projectId: string, filePath: string, copyToStorage: boolean = true) {
    return this.request<VideoData>('/videos/import', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        file_path: filePath,
        copy_to_storage: copyToStorage,
      }),
    });
  }

  async getVideo(videoId: string) {
    return this.request<VideoData>(`/videos/${videoId}`);
  }

  async inspectVideo(videoId: string) {
    return this.request<{ job_id: string; message: string }>(`/videos/${videoId}/inspect`, {
      method: 'POST',
    });
  }

  async generateVideoThumbnail(videoId: string) {
    return this.request<{ job_id: string; message: string }>(`/videos/${videoId}/thumbnail`, {
      method: 'POST',
    });
  }

  async extractVideoAudio(videoId: string) {
    return this.request<{ job_id: string; message: string }>(`/videos/${videoId}/extract-audio`, {
      method: 'POST',
    });
  }

  async generateVideoPreview(videoId: string) {
    return this.request<{ job_id: string; message: string }>(`/videos/${videoId}/generate-preview`, {
      method: 'POST',
    });
  }

  getVideoPreviewUrl(videoId: string): string {
    const token = this.sessionToken ? `?token=${encodeURIComponent(this.sessionToken)}` : '';
    return `${API_BASE_URL}/videos/${videoId}/preview${token}`;
  }

  getVideoThumbnailUrl(videoId: string): string {
    const token = this.sessionToken ? `?token=${encodeURIComponent(this.sessionToken)}` : '';
    return `${API_BASE_URL}/videos/${videoId}/thumbnail-file${token}`;
  }

  // Clips
  async generateClip(data: {
    project_id: string;
    video_id: string;
    title: string;
    start_time: number;
    end_time: number;
    aspect_ratio?: string;
    reframe_mode?: string;
  }) {
    return this.request<ClipData>('/clips/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getClip(clipId: string) {
    return this.request<ClipData>(`/clips/${clipId}`);
  }

  async listProjectClips(projectId: string) {
    return this.request<ClipData[]>(`/clips/project/${projectId}`);
  }

  async deleteClip(clipId: string) {
    return this.request<void>(`/clips/${clipId}`, {
      method: 'DELETE',
    });
  }

  getClipStreamUrl(clipId: string): string {
    const token = this.sessionToken ? `?token=${encodeURIComponent(this.sessionToken)}` : '';
    return `${API_BASE_URL}/clips/${clipId}/stream${token}`;
  }

  getClipThumbnailUrl(clipId: string): string {
    const token = this.sessionToken ? `?token=${encodeURIComponent(this.sessionToken)}` : '';
    return `${API_BASE_URL}/clips/${clipId}/thumbnail${token}`;
  }

  // Background Jobs
  async listJobs(projectId?: string, status?: string) {
    const params = new URLSearchParams();
    if (projectId) params.append('project_id', projectId);
    if (status) params.append('status', status);
    return this.request<JobData[]>(`/jobs?${params.toString()}`);
  }

  async getJob(jobId: string) {
    return this.request<JobData>(`/jobs/${jobId}`);
  }

  async cancelJob(jobId: string) {
    return this.request<JobData>(`/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  }

  async retryJob(jobId: string) {
    return this.request<JobData>(`/jobs/${jobId}/retry`, {
      method: 'POST',
    });
  }

  // AI & Models
  async getInferenceStatus() {
    return this.request<InferenceStatusData>('/system/inference-status');
  }

  async listAiModels() {
    return this.request<WhisperModelData[]>('/ai/models');
  }

  async downloadAiModel(modelName: string) {
    return this.request<{ status: string; model_name: string; local_path: string }>(
      `/ai/models/${modelName}/download`,
      { method: 'POST' }
    );
  }

  async deleteAiModel(modelName: string) {
    return this.request<void>(`/ai/models/${modelName}`, { method: 'DELETE' });
  }

  // Transcription & Transcripts
  async transcribeVideo(videoId: string, config?: {
    model_name?: string;
    language?: string;
    device?: string;
    compute_type?: string;
    vad_filter?: boolean;
    vad_threshold?: number;
    beam_size?: number;
  }) {
    return this.request<{ job_id: string; message: string }>(`/videos/${videoId}/transcribe`, {
      method: 'POST',
      body: JSON.stringify(config || {}),
    });
  }

  async getVideoTranscript(videoId: string) {
    return this.request<TranscriptData>(`/videos/${videoId}/transcript`);
  }

  async getTranscript(transcriptId: string) {
    return this.request<TranscriptData>(`/transcripts/${transcriptId}`);
  }

  async updateTranscript(transcriptId: string, data: { full_text?: string; language?: string }) {
    return this.request<TranscriptData>(`/transcripts/${transcriptId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async getTranscriptSegments(transcriptId: string) {
    return this.request<TranscriptSegmentData[]>(`/transcripts/${transcriptId}/segments`);
  }

  async updateSegmentText(segmentId: string, text: string) {
    return this.request<TranscriptSegmentData>(`/transcripts/segments/${segmentId}`, {
      method: 'PATCH',
      body: JSON.stringify({ text }),
    });
  }

  async retranscribe(transcriptId: string, config?: any) {
    return this.request<{ job_id: string; message: string }>(`/transcripts/${transcriptId}/retranscribe`, {
      method: 'POST',
      body: JSON.stringify(config || {}),
    });
  }

  async deleteTranscript(transcriptId: string) {
    return this.request<void>(`/transcripts/${transcriptId}`, { method: 'DELETE' });
  }

  // --- Phase 5: LLM Models & AI Highlights ---
  async listLlmModels() {
    return this.request<LLMModelData[]>('/ai/llm/models');
  }

  async downloadLlmModel(modelName: string) {
    return this.request<{ status: string; model_id: string; message: string }>(`/ai/llm/models/${modelName}/download`, {
      method: 'POST',
    });
  }

  async deleteLlmModel(modelName: string) {
    return this.request<{ status: string; model_id: string }>(`/ai/llm/models/${modelName}`, {
      method: 'DELETE',
    });
  }

  async getLlmStatus() {
    return this.request<LLMInferenceStatusData>('/ai/llm/status');
  }

  async analyzeHighlights(videoId: string, params: AnalyzeHighlightsParams) {
    return this.request<{ job_id: string; status: string; message: string }>(`/videos/${videoId}/analyze-highlights`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async listHighlightCandidates(videoId: string, status?: string, sortBy: string = 'overall_score') {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (sortBy) params.append('sort_by', sortBy);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this.request<HighlightCandidateData[]>(`/videos/${videoId}/highlight-candidates${qs}`);
  }

  async listProjectHighlights(projectId: string, status?: string) {
    const qs = status ? `?status=${status}` : '';
    return this.request<HighlightCandidateData[]>(`/projects/${projectId}/highlights${qs}`);
  }

  async getHighlightCandidate(candidateId: string) {
    return this.request<HighlightCandidateData>(`/highlights/${candidateId}`);
  }

  async updateHighlightCandidate(
    candidateId: string,
    data: { start_time?: number; end_time?: number; title?: string; summary?: string; hook?: string }
  ) {
    return this.request<HighlightCandidateData>(`/highlights/${candidateId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async approveHighlightCandidate(candidateId: string) {
    return this.request<HighlightCandidateData>(`/highlights/${candidateId}/approve`, {
      method: 'POST',
    });
  }

  async rejectHighlightCandidate(candidateId: string) {
    return this.request<HighlightCandidateData>(`/highlights/${candidateId}/reject`, {
      method: 'POST',
    });
  }

  async createClipFromHighlight(
    candidateId: string,
    data: { aspect_ratio?: string; reframe_mode?: string } = {}
  ) {
    return this.request<{ clip_id: string; job_id: string; status: string; title: string }>(
      `/highlights/${candidateId}/create-clip`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  async deleteHighlightCandidate(candidateId: string) {
    return this.request<{ status: string }>(`/highlights/${candidateId}`, {
      method: 'DELETE',
    });
  }

  // Visual AI & Smart Reframing
  async startVisualAnalysis(
    videoId: string,
    params: {
      sampling_fps?: number;
      confidence_threshold?: number;
      start_time?: number;
      end_time?: number;
      clip_id?: string;
    } = {}
  ) {
    return this.request<{ job_id: string; status: string; message: string; video_id: string }>(
      `/videos/${videoId}/vision/analyze`,
      {
        method: 'POST',
        body: JSON.stringify(params),
      }
    );
  }

  async getVideoVisualAnalysis(videoId: string) {
    return this.request<VisionAnalysisData | null>(`/videos/${videoId}/vision/analysis`);
  }

  async getVisionAnalysisById(analysisId: string) {
    return this.request<VisionAnalysisData>(`/vision/analyses/${analysisId}`);
  }

  async calculateReframeTrajectory(analysisId: string, config: Partial<ReframeConfigData>) {
    return this.request<CropCoordinateData[]>(`/vision/analyses/${analysisId}/trajectory`, {
      method: 'POST',
      body: JSON.stringify({
        aspect_ratio: config.aspect_ratio || '9:16',
        strategy: config.strategy || 'largest_face',
        selected_track_id: config.selected_track_id,
        smoothing_strength: config.smoothing_strength ?? 0.85,
        crop_padding: config.crop_padding ?? 0.15,
        headroom: config.headroom ?? 0.20,
        max_crop_velocity_per_sec: config.max_crop_velocity_per_sec ?? 0.50,
        face_confidence_threshold: config.face_confidence_threshold ?? 0.55,
        sampling_fps: config.sampling_fps ?? 4.0,
      }),
    });
  }

  async addManualCrop(
    analysisId: string,
    crop: {
      timestamp_seconds: number;
      crop_x: number;
      crop_y: number;
      crop_width: number;
      crop_height: number;
    }
  ) {
    return this.request<ManualCropData>(`/vision/analyses/${analysisId}/manual-crops`, {
      method: 'POST',
      body: JSON.stringify(crop),
    });
  }

  async deleteManualCrop(analysisId: string, cropId: string) {
    return this.request<{ success: boolean; message: string }>(
      `/vision/analyses/${analysisId}/manual-crops/${cropId}`,
      {
        method: 'DELETE',
      }
    );
  }

  async getReframePresets() {
    return this.request<ReframePresetData[]>('/vision/presets');
  }

  async createReframePreset(preset: Partial<ReframePresetData>) {
    return this.request<ReframePresetData>('/vision/presets', {
      method: 'POST',
      body: JSON.stringify(preset),
    });
  }

  // Phase 7 Subtitles & Final Render
  async getClipSubtitles(clipId: string) {
    return this.request<SubtitleTrackData>(`/clips/${clipId}/subtitles`);
  }

  async updateClipSubtitleSettings(
    clipId: string,
    settings: { is_enabled?: boolean; preset_id?: string; style_overrides?: any }
  ) {
    return this.request<SubtitleTrackData>(`/clips/${clipId}/subtitles`, {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  }

  async updateSubtitleSegment(
    clipId: string,
    segmentId: string,
    data: { text?: string; start?: number; end?: number; words?: SubtitleWordData[] }
  ) {
    return this.request<SubtitleTrackData>(`/clips/${clipId}/subtitles/segments/${segmentId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async splitSubtitleSegment(clipId: string, segmentId: string, wordIndex: number) {
    return this.request<SubtitleTrackData>(`/clips/${clipId}/subtitles/segments/${segmentId}/split`, {
      method: 'POST',
      body: JSON.stringify({ word_index: wordIndex }),
    });
  }

  async mergeSubtitleSegments(clipId: string, segmentIds: [string, string]) {
    return this.request<SubtitleTrackData>(`/clips/${clipId}/subtitles/merge`, {
      method: 'POST',
      body: JSON.stringify({ segment_ids: segmentIds }),
    });
  }

  async getCaptionPresets() {
    return this.request<CaptionPresetData[]>('/subtitles/presets');
  }

  async saveCaptionPreset(preset: CaptionPresetData) {
    return this.request<CaptionPresetData>('/subtitles/presets', {
      method: 'POST',
      body: JSON.stringify(preset),
    });
  }

  async deleteCaptionPreset(presetId: string) {
    return this.request<{ success: boolean; message: string }>(`/subtitles/presets/${presetId}`, {
      method: 'DELETE',
    });
  }

  async renderClipExport(
    clipId: string,
    config: {
      preset_id?: string;
      resolution?: string;
      fps?: number;
      bitrate_kbps?: number;
      burn_subtitles?: boolean;
      reframe_mode?: string;
      use_vision_tracking?: boolean;
      custom_style?: any;
      codec?: string;
    }
  ) {
    return this.request<{ job_id: string; status: string; clip_id: string; resolution: string; message: string }>(
      `/clips/${clipId}/render`,
      {
        method: 'POST',
        body: JSON.stringify(config),
      }
    );
  }

  async getClipExports(clipId: string) {
    return this.request<ExportData[]>(`/clips/${clipId}/exports`);
  }

  async getProjectExports(projectId: string) {
    return this.request<ExportData[]>(`/projects/${projectId}/exports`);
  }

  async getExportDetails(exportId: string) {
    return this.request<ExportData>(`/exports/${exportId}`);
  }

  async deleteExport(exportId: string) {
    return this.request<{ success: boolean; message: string }>(`/exports/${exportId}`, {
      method: 'DELETE',
    });
  }

  async listAllExports() {
    return this.request<ExportData[]>('/exports');
  }

  async listAllVideos(projectId?: string) {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.request<VideoData[]>(`/videos${query}`);
  }

  getExportStreamUrl(exportId: string): string {
    return `${API_BASE_URL}/exports/${exportId}/stream`;
  }

  getExportDownloadUrl(exportId: string): string {
    return `${API_BASE_URL}/exports/${exportId}/download`;
  }

  // Settings
  async getSettings() {
    return this.request<SettingsData>('/settings');
  }

  async updateSettings(settings: Record<string, any>) {
    return this.request<SettingsData>('/settings', {
      method: 'PATCH',
      body: JSON.stringify({ settings }),
    });
  }

  // Speaker Diarization & Audio Intelligence
  async getSpeakerCapabilities() {
    return this.request<DiarizationCapabilitiesData>('/speakers/capabilities');
  }

  async getLatestAudioAnalysis(videoId: string) {
    return this.request<any>(`/videos/${videoId}/audio-analysis`);
  }

  async startAudioAnalysis(videoId: string, forceReprocess = false) {
    return this.request<{ job_id: string; status: string; message: string }>(
      `/videos/${videoId}/audio-analysis`,
      {
        method: 'POST',
        body: JSON.stringify({ force_reprocess: forceReprocess }),
      }
    );
  }

  async startSpeakerDiarization(analysisId: string, config?: any, forceReprocess = false) {
    return this.request<{ job_id: string; status: string; message: string; analysis_id: string }>(
      `/audio-analysis/${analysisId}/diarize`,
      {
        method: 'POST',
        body: JSON.stringify({ config, force_reprocess: forceReprocess }),
      }
    );
  }

  async getDiarizationSummary(analysisId: string) {
    return this.request<DiarizationSummaryData>(`/audio-analysis/${analysisId}/diarization`);
  }

  async getSpeakersForAnalysis(analysisId: string) {
    return this.request<SpeakerData[]>(`/audio-analysis/${analysisId}/speakers`);
  }

  async getSpeakerTurnsForAnalysis(analysisId: string) {
    return this.request<SpeakerTurnData[]>(`/audio-analysis/${analysisId}/speaker-turns`);
  }

  async updateSpeakerTurn(turnId: string, data: { speaker_id?: string; start_time?: number; end_time?: number; assignment_status?: string }) {
    return this.request<SpeakerTurnData>(`/speaker-turns/${turnId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async updateSpeaker(speakerId: string, data: { display_name?: string; color?: string }) {
    return this.request<SpeakerData>(`/speakers/${speakerId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteDiarization(analysisId: string) {
    return this.request<{ status: string; analysis_id: string }>(`/audio-analysis/${analysisId}/speakers`, {
      method: 'DELETE',
    });
  }

  // Active Speaker Detection & AV Fusion (Phase 8 Stage 4)
  async getActiveSpeakerCapabilities() {
    return this.request<ActiveSpeakerCapabilitiesData>('/active-speakers/capabilities');
  }

  async getVideoActiveSpeakers(videoId: string) {
    return this.request<ActiveSpeakerResponseData>(`/videos/${videoId}/active-speakers`);
  }

  async updateSpeakerFaceAssociation(
    videoId: string,
    speakerId: string,
    data: { face_track_id?: string | null; is_off_screen?: boolean }
  ) {
    return this.request<SpeakerFaceMatchData>(`/videos/${videoId}/speakers/${speakerId}/associate`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteActiveSpeakerAnalysis(videoId: string) {
    return this.request<void>(`/videos/${videoId}/active-speakers`, {
      method: 'DELETE',
    });
  }

  // AI Models
  async listAllModels() {
    return this.request<any[]>('/models');
  }

  // Compositions (Phase 9)
  async autoPlanComposition(params: {
    project_id: string;
    name: string;
    video_id: string;
    candidate_id?: string;
    start_time?: number;
    end_time?: number;
  }) {
    return this.request<any>('/compositions/auto-plan', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async listCompositions(projectId?: string) {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.request<any[]>(`/compositions${query}`);
  }

  async getComposition(compositionId: string) {
    return this.request<any>(`/compositions/${compositionId}`);
  }

  async getCompositionVersions(compositionId: string) {
    return this.request<any[]>(`/compositions/${compositionId}/versions`);
  }

  async createCompositionVersion(compositionId: string, spec: any, commitMessage?: string) {
    return this.request<any>(`/compositions/${compositionId}/versions`, {
      method: 'POST',
      body: JSON.stringify({ spec, commit_message: commitMessage }),
    });
  }

  async compileCompositionRender(compositionId: string, versionId: string) {
    return this.request<any>(`/compositions/${compositionId}/versions/${versionId}/compile`, {
      method: 'POST',
    });
  }

  async submitCompositionRender(compositionId: string, versionId: string, profile?: any) {
    return this.request<any>(`/compositions/${compositionId}/versions/${versionId}/renders`, {
      method: 'POST',
      body: JSON.stringify(profile || {}),
    });
  }

  async listCompositionRenders(compositionId: string) {
    return this.request<any[]>(`/compositions/${compositionId}/renders`);
  }

  async getCompositionRenderStatus(compositionId: string, renderId: string) {
    return this.request<any>(`/compositions/${compositionId}/renders/${renderId}`);
  }

  async cancelCompositionRender(compositionId: string, renderId: string) {
    return this.request<any>(`/compositions/${compositionId}/renders/${renderId}/cancel`, {
      method: 'POST',
    });
  }

  async getCompositionRenderArtifacts(compositionId: string, renderId: string) {
    return this.request<any[]>(`/compositions/${compositionId}/renders/${renderId}/artifacts`);
  }
}

export interface SpeakerData {
  id: string;
  project_id: string;
  analysis_id?: string;
  speaker_identifier?: string;
  label: string;
  display_name?: string;
  color?: string;
  total_speech_duration: number;
  turn_count: number;
  model_name: string;
  model_version: string;
  created_at?: string;
  updated_at?: string;
}

export interface SpeakerTurnData {
  id: string;
  analysis_id: string;
  speaker_id?: string;
  speaker_identifier?: string;
  display_name?: string;
  color?: string;
  start_time: number;
  end_time: number;
  duration: number;
  confidence: number;
  assignment_status: string;
  created_at?: string;
  updated_at?: string;
}

export interface DiarizationSummaryData {
  analysis_id: string;
  status: string;
  num_speakers: number;
  total_speech_duration: number;
  speakers: SpeakerData[];
  speaker_turns: SpeakerTurnData[];
  silhouette_score?: number;
  processing_duration_seconds: number;
  processing_device: string;
}

export interface DiarizationCapabilitiesData {
  diarization_available: boolean;
  model_name: string;
  embedding_dimension: number;
  sample_rate: number;
  execution_device: string;
  clustering_algorithm: string;
  default_config: {
    distance_threshold: number;
    expected_speakers?: number;
    min_speakers: number;
    max_speakers: number;
    window_duration_sec: number;
    step_duration_sec: number;
    collar_sec: number;
  };
}

export interface ActiveSpeakerSegmentData {
  id?: string;
  start_time: number;
  end_time: number;
  duration: number;
  face_track_id?: string | null;
  speaker_id?: string | null;
  confidence: number;
  speaking_score: number;
  state: string; // active_speaker, silent_listener, off_screen_speaker, unknown, overlapping
}

export interface SpeakerFaceMatchData {
  id?: string;
  speaker_id: string;
  face_track_id?: string | null;
  confidence: number;
  overlap_duration: number;
  turn_consistency?: number;
  status?: string; // confirmed, provisional, off_screen, unknown
  turns_matched?: number;
  total_turns?: number;
  is_manual: boolean;
  is_off_screen: boolean;
  evidence_notes?: string | null;
}

export interface ActiveSpeakerResponseData {
  video_id: string;
  active_segments: ActiveSpeakerSegmentData[];
  associations: SpeakerFaceMatchData[];
  total_active_speech_seconds: number;
}

export interface ActiveSpeakerCapabilitiesData {
  model_name: string;
  framework: string;
  face_mesh_points: number;
  asd_parameter_count: string;
  offline_only: boolean;
  supports_manual_override: boolean;
}

export const api = new ApiService();
