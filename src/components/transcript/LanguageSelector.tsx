import React from 'react';
import { Globe } from 'lucide-react';

interface LanguageSelectorProps {
  value: string;
  onChange: (lang: string) => void;
  className?: string;
}

const COMMON_LANGUAGES = [
  { code: '', label: 'Auto-Detect Language' },
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Spanish' },
  { code: 'fr', label: 'French' },
  { code: 'de', label: 'German' },
  { code: 'it', label: 'Italian' },
  { code: 'pt', label: 'Portuguese' },
  { code: 'nl', label: 'Dutch' },
  { code: 'ja', label: 'Japanese' },
  { code: 'zh', label: 'Chinese' },
  { code: 'ru', label: 'Russian' },
  { code: 'ar', label: 'Arabic' },
  { code: 'hi', label: 'Hindi' },
];

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  value,
  onChange,
  className = '',
}) => {
  return (
    <div className={`relative ${className}`}>
      <div className="flex items-center gap-1.5 bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 focus-within:border-indigo-500">
        <Globe className="w-3.5 h-3.5 text-zinc-400 flex-shrink-0" />
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-transparent text-xs text-white focus:outline-none cursor-pointer"
        >
          {COMMON_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code} className="bg-zinc-900 text-white">
              {lang.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};
