import React from 'react';
import { Cpu, Download, CheckCircle2 } from 'lucide-react';
import { WhisperModelData } from '../../services/api';

interface ModelSelectorProps {
  models: WhisperModelData[];
  selectedModel: string;
  onSelectModel: (modelId: string) => void;
  className?: string;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  models,
  selectedModel,
  onSelectModel,
  className = '',
}) => {
  return (
    <div className={`relative ${className}`}>
      <div className="flex items-center gap-1.5 bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 focus-within:border-indigo-500">
        <Cpu className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
        <select
          value={selectedModel}
          onChange={(e) => onSelectModel(e.target.value)}
          className="w-full bg-transparent text-xs text-white focus:outline-none cursor-pointer"
        >
          {models.map((m) => (
            <option key={m.model_id} value={m.model_id} className="bg-zinc-900 text-white">
              {m.display_name} ({m.parameter_count}) - {m.is_installed ? 'Installed' : `~${m.disk_size_mb}MB`}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};
