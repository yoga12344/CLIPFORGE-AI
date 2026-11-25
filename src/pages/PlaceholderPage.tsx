import React from 'react';
import { LucideIcon } from 'lucide-react';

interface PlaceholderPageProps {
  title: string;
  description: string;
  icon: LucideIcon;
  badge?: string;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({
  title,
  description,
  icon: Icon,
  badge = 'Planned for Phase 2+',
}) => {
  return (
    <div className="max-w-4xl mx-auto space-y-6 pt-6">
      <div className="flex items-center justify-between border-b border-[#1f1f2b] pb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white flex items-center gap-2">
              {title}
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                {badge}
              </span>
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">{description}</p>
          </div>
        </div>
      </div>

      <div className="p-8 bg-[#14141d] border border-[#20202e] rounded-2xl text-center space-y-3">
        <p className="text-sm font-semibold text-zinc-300">Phase 1 Infrastructure Active</p>
        <p className="text-xs text-zinc-500 max-w-md mx-auto">
          The SQLite database schema, secure desktop IPC bridge, and hardware telemetry engine are connected and operational. This module activates in the upcoming Phase.
        </p>
      </div>
    </div>
  );
};
