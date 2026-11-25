import React, { useEffect, useState } from 'react';
import {
  Type,
  Palette,
  Sparkles,
  Sliders,
  Film,
  Download,
  AlertCircle,
  Loader2,
  Check,
} from 'lucide-react';
import {
  api,
  CaptionPresetData,
  SubtitleSegmentData,
  SubtitleTrackData,
} from '../../services/api';
import { CaptionPresetGallery } from './CaptionPresetGallery';
import { CaptionStyleEditor } from './CaptionStyleEditor';
import { SubtitleEditor } from './SubtitleEditor';
import { ExportModal } from './ExportModal';

interface SubtitlePanelProps {
  clipId?: string;
  clipTitle?: string;
  currentTime: number;
  onSeek: (seconds: number) => void;
  onTrackLoaded?: (track: SubtitleTrackData) => void;
  onPresetChange?: (preset: CaptionPresetData) => void;
}

export const SubtitlePanel: React.FC<SubtitlePanelProps> = ({
  clipId,
  clipTitle = 'Approved Clip',
  currentTime,
  onSeek,
  onTrackLoaded,
  onPresetChange,
}) => {
  const [track, setTrack] = useState<SubtitleTrackData | null>(null);
  const [presets, setPresets] = useState<CaptionPresetData[]>([]);
  const [activePreset, setActivePreset] = useState<CaptionPresetData | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'editor' | 'styles' | 'presets'>('editor');
  const [isLoading, setIsLoading] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!clipId) return;
    setIsLoading(true);
    setError(null);
    try {
      // 1. Fetch presets
      const allPresets = await api.getCaptionPresets();
      setPresets(allPresets);

      // 2. Fetch or create subtitle track for this clip
      const subTrack = await api.getClipSubtitles(clipId);
      setTrack(subTrack);
      if (onTrackLoaded) onTrackLoaded(subTrack);

      // 3. Resolve active preset
      let chosenPreset = subTrack.preset || allPresets.find((p) => p.is_default) || allPresets[0];
      if (subTrack.style_overrides) {
        chosenPreset = { ...chosenPreset, ...subTrack.style_overrides };
      }
      setActivePreset(chosenPreset);
      if (onPresetChange) onPresetChange(chosenPreset);
    } catch (e: any) {
      console.warn('Failed to load subtitles:', e);
      setError(e.message || 'Failed to load subtitles for this clip');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [clipId]);

  const handleSelectPreset = async (preset: CaptionPresetData) => {
    if (!clipId) return;
    setActivePreset(preset);
    if (onPresetChange) onPresetChange(preset);
    try {
      await api.updateClipSubtitleSettings(clipId, {
        preset_id: preset.id,
        style_overrides: null,
      });
    } catch (e) {
      console.warn('Failed to update preset:', e);
    }
  };

  const handleCustomStyleChange = async (updated: CaptionPresetData) => {
    setActivePreset(updated);
    if (onPresetChange) onPresetChange(updated);
    if (clipId) {
      try {
        await api.updateClipSubtitleSettings(clipId, {
          style_overrides: updated,
        });
      } catch (e) {
        console.warn('Failed to update custom style overrides:', e);
      }
    }
  };

  const handleUpdateSegment = async (
    segmentId: string,
    updated: Partial<SubtitleSegmentData>
  ) => {
    if (!clipId) return;
    try {
      const refreshed = await api.updateSubtitleSegment(clipId, segmentId, updated);
      setTrack(refreshed);
      if (onTrackLoaded) onTrackLoaded(refreshed);
    } catch (e: any) {
      console.warn('Failed to update segment:', e);
    }
  };

  const handleSplitSegment = async (segmentId: string, wordIndex: number) => {
    if (!clipId) return;
    try {
      const refreshed = await api.splitSubtitleSegment(clipId, segmentId, wordIndex);
      setTrack(refreshed);
      if (onTrackLoaded) onTrackLoaded(refreshed);
    } catch (e: any) {
      console.warn('Failed to split segment:', e);
    }
  };

  const handleMergeSegments = async (segId1: string, segId2: string) => {
    if (!clipId) return;
    try {
      const refreshed = await api.mergeSubtitleSegments(clipId, [segId1, segId2]);
      setTrack(refreshed);
      if (onTrackLoaded) onTrackLoaded(refreshed);
    } catch (e: any) {
      console.warn('Failed to merge segments:', e);
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface-base border-l border-border-base">
      {/* Top Header */}
      <div className="p-4 border-b border-border-base flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Type className="w-4 h-4 text-primary" />
          <h3 className="font-semibold text-sm text-text-primary">Subtitles & Karaoke</h3>
        </div>

        {clipId && (
          <button
            onClick={() => setIsExportModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary hover:bg-primary/90 text-black font-semibold text-xs rounded-lg transition-all shadow-md"
          >
            <Film className="w-3.5 h-3.5" />
            <span>Export Clip</span>
          </button>
        )}
      </div>

      {/* Subtab Navigation: Editor vs Presets vs Custom Styling */}
      <div className="flex items-center gap-1 p-2 bg-surface-muted/30 border-b border-border-base text-xs">
        <button
          onClick={() => setActiveSubTab('editor')}
          className={`flex-1 py-1.5 rounded-lg font-medium transition-colors ${
            activeSubTab === 'editor'
              ? 'bg-surface-base text-text-primary shadow-sm border border-border-muted'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          Transcript Words
        </button>
        <button
          onClick={() => setActiveSubTab('presets')}
          className={`flex-1 py-1.5 rounded-lg font-medium transition-colors ${
            activeSubTab === 'presets'
              ? 'bg-surface-base text-text-primary shadow-sm border border-border-muted'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          Preset Styles
        </button>
        <button
          onClick={() => setActiveSubTab('styles')}
          className={`flex-1 py-1.5 rounded-lg font-medium transition-colors ${
            activeSubTab === 'styles'
              ? 'bg-surface-base text-text-primary shadow-sm border border-border-muted'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          Custom Style
        </button>
      </div>

      {/* Main Tab Content Area */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && (
          <div className="flex flex-col items-center justify-center p-8 text-text-muted text-xs">
            <Loader2 className="w-6 h-6 animate-spin text-primary mb-2" />
            <span>Loading subtitle track...</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-xs mb-3">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!clipId ? (
          <div className="p-8 text-center text-text-muted text-xs">
            <Type className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <span>Select or generate a clip to edit subtitles and render final video.</span>
          </div>
        ) : (
          <>
            {activeSubTab === 'editor' && track && (
              <SubtitleEditor
                segments={track.segments || []}
                currentTime={currentTime}
                onSeek={onSeek}
                onUpdateSegment={handleUpdateSegment}
                onSplitSegment={handleSplitSegment}
                onMergeSegments={handleMergeSegments}
              />
            )}

            {activeSubTab === 'presets' && (
              <CaptionPresetGallery
                presets={presets}
                selectedPresetId={activePreset?.id}
                onSelectPreset={handleSelectPreset}
              />
            )}

            {activeSubTab === 'styles' && activePreset && (
              <CaptionStyleEditor
                style={activePreset}
                onChange={handleCustomStyleChange}
              />
            )}
          </>
        )}
      </div>

      {/* Export Render Modal */}
      {clipId && (
        <ExportModal
          isOpen={isExportModalOpen}
          onClose={() => setIsExportModalOpen(false)}
          clipId={clipId}
          clipTitle={clipTitle}
          activePreset={activePreset || undefined}
        />
      )}
    </div>
  );
};
