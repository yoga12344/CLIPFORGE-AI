import React from 'react';
import { Ratio, Sliders, Users, User, Target, Compass } from 'lucide-react';
import { ReframeConfigData, TrackedFaceData } from '../../services/api';

interface ReframeSettingsPanelProps {
  config: ReframeConfigData;
  onChange: (newConfig: ReframeConfigData) => void;
  tracks: TrackedFaceData[];
}

export const ReframeSettingsPanel: React.FC<ReframeSettingsPanelProps> = ({
  config,
  onChange,
  tracks,
}) => {
  const aspectRatios = [
    { id: '9:16', label: '9:16 (TikTok/Reels)', icon: '📱' },
    { id: '1:1', label: '1:1 (Square)', icon: '⏹' },
    { id: '4:5', label: '4:5 (Portrait)', icon: '🖼' },
    { id: '16:9', label: '16:9 (Landscape)', icon: '🖥' },
  ];

  const strategies = [
    { id: 'largest_face', label: 'Dominant Speaker', icon: User, desc: 'Focus on primary/closest face' },
    { id: 'center_face', label: 'Center Face', icon: Target, desc: 'Keep center-stage speaker framed' },
    { id: 'group', label: 'Group Framing', icon: Users, desc: 'Keep all detected subjects in view' },
    { id: 'manual_track', label: 'Selected Track', icon: Compass, desc: 'Lock onto a specific subject ID' },
  ];

  return (
    <div className="space-y-4 text-xs">
      {/* 1. Target Aspect Ratio */}
      <div>
        <label className="flex items-center gap-1.5 text-text-muted font-semibold uppercase tracking-wider mb-2">
          <Ratio className="w-3.5 h-3.5 text-primary" />
          <span>Target Aspect Ratio</span>
        </label>
        <div className="grid grid-cols-2 gap-2">
          {aspectRatios.map((ratio) => (
            <button
              key={ratio.id}
              onClick={() => onChange({ ...config, aspect_ratio: ratio.id })}
              className={`flex items-center gap-2 p-2 rounded-lg border text-left transition-all ${
                config.aspect_ratio === ratio.id
                  ? 'border-primary bg-primary/10 text-text-primary font-medium'
                  : 'border-border-muted bg-surface-muted/40 text-text-muted hover:border-border-base'
              }`}
            >
              <span>{ratio.icon}</span>
              <span className="truncate">{ratio.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 2. Framing Strategy */}
      <div>
        <label className="flex items-center gap-1.5 text-text-muted font-semibold uppercase tracking-wider mb-2">
          <Sliders className="w-3.5 h-3.5 text-primary" />
          <span>Framing Strategy</span>
        </label>
        <div className="grid grid-cols-2 gap-2">
          {strategies.map((strat) => {
            const Icon = strat.icon;
            const isSelected = config.strategy === strat.id;
            return (
              <button
                key={strat.id}
                onClick={() => onChange({ ...config, strategy: strat.id })}
                className={`p-2 rounded-lg border text-left transition-all ${
                  isSelected
                    ? 'border-primary bg-primary/10 text-text-primary font-medium'
                    : 'border-border-muted bg-surface-muted/40 text-text-muted hover:border-border-base'
                }`}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <Icon className={`w-3.5 h-3.5 ${isSelected ? 'text-primary' : 'text-text-muted'}`} />
                  <span className="font-medium">{strat.label}</span>
                </div>
                <div className="text-[10px] text-text-muted truncate">{strat.desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Manual Subject Track Picker (if strategy is manual_track) */}
      {config.strategy === 'manual_track' && (
        <div className="p-2.5 rounded-lg border border-border-muted bg-surface-muted/30">
          <label className="block text-text-muted font-medium mb-1.5">Select Subject to Lock Onto</label>
          <div className="flex flex-wrap gap-1.5">
            {tracks.length === 0 ? (
              <span className="text-text-muted italic">No face tracks available. Run visual analysis first.</span>
            ) : (
              tracks.map((t) => (
                <button
                  key={t.track_id}
                  onClick={() => onChange({ ...config, selected_track_id: t.track_id })}
                  className={`px-2.5 py-1 rounded border text-[11px] ${
                    config.selected_track_id === t.track_id
                      ? 'border-primary bg-primary text-black font-semibold'
                      : 'border-border-muted bg-surface-base text-text-secondary hover:border-primary/50'
                  }`}
                >
                  {t.track_id} ({t.detection_count} frames)
                </button>
              ))
            )}
          </div>
        </div>
      )}

      {/* 4. Motion Smoothing & Camera Velocity Sliders */}
      <div className="space-y-3 pt-2 border-t border-border-base">
        <div>
          <div className="flex justify-between text-text-muted mb-1">
            <span>Camera Smoothing (EMA)</span>
            <span className="text-text-primary font-mono">{Math.round(config.smoothing_strength * 100)}%</span>
          </div>
          <input
            type="range"
            min="0.10"
            max="0.95"
            step="0.05"
            value={config.smoothing_strength}
            onChange={(e) => onChange({ ...config, smoothing_strength: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-text-muted">
            <span>Responsive / Rapid</span>
            <span>Smooth Cinematic</span>
          </div>
        </div>

        <div>
          <div className="flex justify-between text-text-muted mb-1">
            <span>Subject Headroom Margin</span>
            <span className="text-text-primary font-mono">{Math.round(config.headroom * 100)}%</span>
          </div>
          <input
            type="range"
            min="0.05"
            max="0.35"
            step="0.05"
            value={config.headroom}
            onChange={(e) => onChange({ ...config, headroom: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
        </div>

        <div>
          <div className="flex justify-between text-text-muted mb-1">
            <span>Max Camera Speed / Sec</span>
            <span className="text-text-primary font-mono">{Math.round(config.max_crop_velocity_per_sec * 100)}%</span>
          </div>
          <input
            type="range"
            min="0.20"
            max="1.00"
            step="0.05"
            value={config.max_crop_velocity_per_sec}
            onChange={(e) => onChange({ ...config, max_crop_velocity_per_sec: parseFloat(e.target.value) })}
            className="w-full accent-primary"
          />
        </div>
      </div>
    </div>
  );
};
