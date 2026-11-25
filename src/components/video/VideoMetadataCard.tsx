import React from 'react';
import { 
  FileVideo, Film, Volume2, HardDrive, Cpu, 
  Sparkles, RefreshCw, Scissors, Image as ImageIcon 
} from 'lucide-react';
import { VideoData } from '../../services/api';

interface VideoMetadataCardProps {
  video: VideoData;
  onGeneratePreview: () => void;
  onExtractAudio: () => void;
  onGenerateThumbnail: () => void;
  onInspect: () => void;
  isProcessing?: boolean;
}

export const VideoMetadataCard: React.FC<VideoMetadataCardProps> = ({
  video,
  onGeneratePreview,
  onExtractAudio,
  onGenerateThumbnail,
  onInspect,
  isProcessing = false,
}) => {
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-lg">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-indigo-400">
            <FileVideo className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-white font-semibold text-sm truncate max-w-xs md:max-w-md">
              {video.filename}
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Duration: {formatDuration(video.duration_seconds)} • {formatBytes(video.file_size_bytes)}
            </p>
          </div>
        </div>

        <button
          onClick={onInspect}
          disabled={isProcessing}
          className="p-1.5 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 rounded-lg transition-colors"
          title="Re-inspect with FFprobe"
        >
          <RefreshCw className={`w-4 h-4 ${isProcessing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Grid Specs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-3 border-y border-zinc-800/80 mb-4 text-xs">
        <div>
          <span className="text-zinc-500 flex items-center gap-1">
            <Film className="w-3.5 h-3.5" /> Resolution
          </span>
          <p className="font-medium text-zinc-200 mt-0.5 font-mono">
            {video.width} × {video.height}
          </p>
        </div>

        <div>
          <span className="text-zinc-500 flex items-center gap-1">
            <Cpu className="w-3.5 h-3.5" /> Video Codec
          </span>
          <p className="font-medium text-zinc-200 mt-0.5 font-mono uppercase">
            {video.video_codec || 'N/A'} @ {video.fps} fps
          </p>
        </div>

        <div>
          <span className="text-zinc-500 flex items-center gap-1">
            <Volume2 className="w-3.5 h-3.5" /> Audio Track
          </span>
          <p className="font-medium text-zinc-200 mt-0.5 font-mono uppercase">
            {video.has_audio ? (video.audio_codec || 'Audio Available') : 'No Audio'}
          </p>
        </div>

        <div>
          <span className="text-zinc-500 flex items-center gap-1">
            <HardDrive className="w-3.5 h-3.5" /> Format
          </span>
          <p className="font-medium text-zinc-200 mt-0.5 font-mono uppercase">
            {video.format || 'MP4'}
          </p>
        </div>
      </div>

      {/* Action Pipeline Buttons */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onGeneratePreview}
          disabled={isProcessing}
          className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
        >
          <Film className="w-3.5 h-3.5 text-indigo-400" />
          Generate 720p Proxy
        </button>

        <button
          onClick={onExtractAudio}
          disabled={isProcessing}
          className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
        >
          <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
          Extract 16kHz WAV
        </button>

        <button
          onClick={onGenerateThumbnail}
          disabled={isProcessing}
          className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
        >
          <ImageIcon className="w-3.5 h-3.5 text-amber-400" />
          Generate Thumbnails
        </button>
      </div>
    </div>
  );
};
