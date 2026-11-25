import React from 'react';
import { useToastStore, ToastType } from '../../store/toastStore';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

const icons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
  error: <AlertCircle className="w-4 h-4 text-rose-400" />,
  warning: <AlertTriangle className="w-4 h-4 text-amber-400" />,
  info: <Info className="w-4 h-4 text-indigo-400" />,
};

const borderStyles: Record<ToastType, string> = {
  success: 'border-emerald-500/30 bg-[#121c16]',
  error: 'border-rose-500/30 bg-[#1c1214]',
  warning: 'border-amber-500/30 bg-[#1c1a12]',
  info: 'border-indigo-500/30 bg-[#141422]',
};

export const ToastContainer: React.FC = () => {
  const { toasts, dismiss } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-12 right-6 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-start gap-3 p-3.5 rounded-xl border shadow-xl backdrop-blur transition-all duration-200 animate-in fade-in slide-in-from-bottom-2 ${
            borderStyles[toast.type]
          }`}
        >
          <div className="mt-0.5 flex-shrink-0">{icons[toast.type]}</div>
          <div className="flex-1 space-y-0.5">
            <h4 className="text-xs font-bold text-white">{toast.title}</h4>
            {toast.message && (
              <p className="text-[11px] text-zinc-300 leading-snug">{toast.message}</p>
            )}
          </div>
          <button
            onClick={() => dismiss(toast.id)}
            className="text-zinc-500 hover:text-zinc-300 p-0.5 rounded transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
};
