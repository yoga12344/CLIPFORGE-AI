import React from 'react';
import { ScoreBreakdownData } from '../../services/api';
import { Sparkles, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface HighlightScoreBreakdownProps {
  scoreBreakdown?: ScoreBreakdownData;
  overallScore: number;
}

export const HighlightScoreBreakdown: React.FC<HighlightScoreBreakdownProps> = ({
  scoreBreakdown,
  overallScore,
}) => {
  if (!scoreBreakdown) {
    return (
      <div className="text-xs text-zinc-500 py-2">
        No detailed breakdown available for this candidate.
      </div>
    );
  }

  const dimensions = [
    { label: 'Hook Strength', score: scoreBreakdown.hook_strength, max: 20, color: 'bg-indigo-500' },
    { label: 'Content Value', score: scoreBreakdown.content_value, max: 20, color: 'bg-emerald-500' },
    { label: 'Narrative Flow', score: scoreBreakdown.narrative_completeness, max: 20, color: 'bg-cyan-500' },
    { label: 'Standalone Context', score: scoreBreakdown.standalone_context, max: 15, color: 'bg-blue-500' },
    { label: 'Interest & Depth', score: scoreBreakdown.interest_level, max: 10, color: 'bg-purple-500' },
    { label: 'Conciseness', score: scoreBreakdown.conciseness, max: 10, color: 'bg-amber-500' },
    { label: 'Ending Quality', score: scoreBreakdown.ending_quality, max: 5, color: 'bg-rose-500' },
  ];

  return (
    <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3 space-y-3 text-xs">
      <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2">
        <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          Score Evaluation
        </span>
        <span className="font-mono font-bold text-sm text-indigo-400">
          {overallScore} / 100
        </span>
      </div>

      {/* Progress Bars */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
        {dimensions.map((dim) => (
          <div key={dim.label} className="space-y-1">
            <div className="flex justify-between text-[11px] text-zinc-400">
              <span>{dim.label}</span>
              <span className="font-mono text-zinc-300">
                {dim.score} / {dim.max}
              </span>
            </div>
            <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
              <div
                className={`h-full rounded-full ${dim.color} transition-all duration-300`}
                style={{ width: `${Math.min(100, (dim.score / dim.max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Strengths & Penalties */}
      {(scoreBreakdown.strengths.length > 0 || scoreBreakdown.penalties.length > 0) && (
        <div className="pt-2 border-t border-zinc-800/60 space-y-1.5">
          {scoreBreakdown.strengths.map((str, i) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px] text-emerald-400">
              <CheckCircle2 className="w-3 h-3 flex-shrink-0" />
              <span>{str}</span>
            </div>
          ))}
          {scoreBreakdown.penalties.map((pen, i) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px] text-amber-400/90">
              <AlertTriangle className="w-3 h-3 flex-shrink-0" />
              <span>{pen}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
