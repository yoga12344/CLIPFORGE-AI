import { create } from 'zustand';
import { api, SettingsData } from '../services/api';
import { useToastStore } from './toastStore';

interface SettingsState {
  settings: SettingsData | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;

  fetchSettings: () => Promise<void>;
  updateSettings: (updates: Partial<SettingsData>) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: null,
  isLoading: false,
  isSaving: false,
  error: null,

  fetchSettings: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await api.getSettings();
      set({ settings: data, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  updateSettings: async (updates) => {
    set({ isSaving: true });
    try {
      const updated = await api.updateSettings(updates);
      set({ settings: updated, isSaving: false });
      useToastStore.getState().show('success', 'Settings Saved', 'Application preferences updated.');
    } catch (err: any) {
      set({ isSaving: false });
      useToastStore.getState().show('error', 'Save Failed', err.message);
      throw err;
    }
  },
}));
