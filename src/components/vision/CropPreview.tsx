import React from 'react';
import { Smartphone, Ratio } from 'lucide-react';
import { CropCoordinateData } from '../../services/api';

interface CropPreviewProps {
  videoSrc: string;
  currentTime: number;
  currentCrop?: CropCoordinateData | null;
  aspectRatio?: string;
}

export const CropPreview: React.FC<CropPreviewProps> = ({
  videoSrc,
  currentTime,
  currentCrop,
  aspectRatio = '9:16',
}) => {
  // Compute object position percent from crop coordinate
  const posX = currentCrop ? Math.max(0, Math.min(100, (currentCrop.crop_x / (1 - (currentCrop.crop_width || 0.316))) * 100)) : 50;
  const posY = currentCrop ? Math.max(0, Math.min(100, (currentCrop.crop_y / Math.max(0.01, 1 - (currentCrop.crop_height || 1.0))) * 100)) : 50;

  // Aspect ratio aspect class
  const aspectClass =
    aspectRatio === '9:16'
      ? 'aspect-[9/16] w-48'
      : aspectRatio === '1:1'
      ? 'aspect-square w-56'
      : aspectRatio === '4:5'
      ? 'aspect-[4/5] w-52'
      : 'aspect-[16/9] w-72';

  return (
    <div className="flex flex-col items-center justify-center p-3 bg-surface-base/80 border border-border-base rounded-xl">
      <div className="flex items-center gap-1.5 mb-2 text-text-muted text-xs font-medium">
        <Smartphone className="w-3.5 h-3.5 text-primary" />
        <span>Live Reframe Preview ({aspectRatio})</span>
      </div>

      <div
        className={`relative ${aspectClass} rounded-lg overflow-hidden border border-border-muted bg-black shadow-lg flex items-center justify-center`}
      >
        {videoSrc ? (
          <video
            src={videoSrc}
            className="w-full h-full object-cover pointer-events-none"
            style={{
              objectPosition: `${posX}% ${posY}%`,
            }}
            muted
            playsInline
            ref={(ref) => {
              if (ref && Math.abs(ref.currentTime - currentTime) > 0.2) {
                ref.currentTime = currentTime;
              }
            }}
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-text-muted text-xs p-4 text-center">
            <Ratio className="w-6 h-6 mb-1 opacity-40" />
            <span>Load a video to preview vertical crop</span>
          </div>
        )}

        {/* Framing border indicator */}
        <div className="absolute inset-0 pointer-events-none border border-white/10 rounded-lg" />
      </div>
    </div>
  );
};
