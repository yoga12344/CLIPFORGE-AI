import React from 'react';
import { TrackedFaceData, CropCoordinateData } from '../../services/api';

interface FaceDetectionOverlayProps {
  currentTime: number;
  tracks: TrackedFaceData[];
  currentCrop?: CropCoordinateData | null;
  selectedTrackId?: string;
  showFaces?: boolean;
  showCropBox?: boolean;
}

export const FaceDetectionOverlay: React.FC<FaceDetectionOverlayProps> = ({
  currentTime,
  tracks,
  currentCrop,
  selectedTrackId,
  showFaces = true,
  showCropBox = true,
}) => {
  // Find samples active at currentTime
  const activeFaces = tracks
    .map((track) => {
      // Find sample closest to currentTime (within 0.3s)
      const sample = (track as any).samples?.find(
        (s: any) => Math.abs(s.timestamp_seconds - currentTime) <= 0.3
      );
      if (!sample) return null;
      return {
        trackId: track.track_id,
        confidence: sample.confidence,
        bbox: sample.bbox,
        isSelected: track.track_id === selectedTrackId,
      };
    })
    .filter(Boolean);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-10">
      {/* 1. Crop Framing Window Outline */}
      {showCropBox && currentCrop && (
        <div
          className="absolute border-2 border-primary/90 shadow-[0_0_15px_rgba(250,204,21,0.4)] transition-all duration-150 ease-out"
          style={{
            left: `${currentCrop.crop_x * 100}%`,
            top: `${currentCrop.crop_y * 100}%`,
            width: `${currentCrop.crop_width * 100}%`,
            height: `${currentCrop.crop_height * 100}%`,
          }}
        >
          {/* Dimmed letterbox bars outside crop */}
          <div className="absolute -top-1 -left-1 px-1.5 py-0.5 bg-primary text-black text-[10px] font-bold rounded-sm tracking-wider uppercase">
            {currentCrop.reframing_mode === 'auto_tracking' ? 'AI Focus' : 'Center'}
          </div>

          {/* Rule of thirds grid lines */}
          <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 opacity-20 pointer-events-none">
            <div className="border-r border-b border-primary/50" />
            <div className="border-r border-b border-primary/50" />
            <div className="border-b border-primary/50" />
            <div className="border-r border-b border-primary/50" />
            <div className="border-r border-b border-primary/50" />
            <div className="border-b border-primary/50" />
            <div className="border-r border-primary/50" />
            <div className="border-r border-primary/50" />
            <div />
          </div>
        </div>
      )}

      {/* 2. Face Bounding Boxes */}
      {showFaces &&
        activeFaces.map((face: any, idx: number) => {
          const { bbox, trackId, isSelected, confidence } = face;
          const borderColor = isSelected
            ? 'border-primary shadow-[0_0_10px_rgba(250,204,21,0.5)]'
            : 'border-emerald-400/80';
          const badgeBg = isSelected ? 'bg-primary text-black' : 'bg-emerald-500 text-white';

          return (
            <div
              key={`${trackId}-${idx}`}
              className={`absolute border-2 ${borderColor} rounded-sm transition-all duration-100`}
              style={{
                left: `${bbox.x * 100}%`,
                top: `${bbox.y * 100}%`,
                width: `${bbox.width * 100}%`,
                height: `${bbox.height * 100}%`,
              }}
            >
              <div
                className={`absolute -top-5 left-0 px-1 py-0.2 text-[9px] font-semibold rounded-t-sm whitespace-nowrap ${badgeBg}`}
              >
                {trackId} ({Math.round(confidence * 100)}%)
              </div>
            </div>
          );
        })}
    </div>
  );
};
