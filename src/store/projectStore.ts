import { create } from 'zustand';
import { api, ProjectData, DashboardStatsData } from '../services/api';
import { useToastStore } from './toastStore';

interface ProjectState {
  projects: ProjectData[];
  selectedProject: ProjectData | null;
  dashboardStats: DashboardStatsData | null;
  searchQuery: string;
  sortBy: string;
  sortOrder: string;
  viewMode: 'grid' | 'list';
  isLoading: boolean;
  error: string | null;

  setSearchQuery: (query: string) => void;
  setSortBy: (sortBy: string) => void;
  setSortOrder: (order: string) => void;
  setViewMode: (mode: 'grid' | 'list') => void;
  setSelectedProject: (project: ProjectData | null) => void;

  fetchDashboardStats: () => Promise<void>;
  fetchProjects: () => Promise<void>;
  createProject: (name: string, description?: string) => Promise<ProjectData>;
  updateProject: (id: string, name: string, description?: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  selectedProject: null,
  dashboardStats: null,
  searchQuery: '',
  sortBy: 'updated_at',
  sortOrder: 'desc',
  viewMode: 'grid',
  isLoading: false,
  error: null,

  setSearchQuery: (query) => {
    set({ searchQuery: query });
    get().fetchProjects();
  },

  setSortBy: (sortBy) => {
    set({ sortBy });
    get().fetchProjects();
  },

  setSortOrder: (sortOrder) => {
    set({ sortOrder });
    get().fetchProjects();
  },

  setViewMode: (viewMode) => set({ viewMode }),
  setSelectedProject: (project) => set({ selectedProject: project }),

  fetchDashboardStats: async () => {
    try {
      const stats = await api.getDashboardStats();
      set({ dashboardStats: stats });
    } catch (err: any) {
      console.error('Failed to fetch dashboard stats:', err);
    }
  },

  fetchProjects: async () => {
    set({ isLoading: true, error: null });
    const { searchQuery, sortBy, sortOrder } = get();
    try {
      const list = await api.listProjects(searchQuery, sortBy, sortOrder);
      set({ projects: list, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  createProject: async (name: string, description?: string) => {
    try {
      const newProj = await api.createProject(name, description);
      await get().fetchProjects();
      await get().fetchDashboardStats();
      useToastStore.getState().show('success', 'Project Created', `Project "${name}" is ready.`);
      return newProj;
    } catch (err: any) {
      useToastStore.getState().show('error', 'Creation Failed', err.message);
      throw err;
    }
  },

  updateProject: async (id: string, name: string, description?: string) => {
    try {
      await api.updateProject(id, { name, description });
      await get().fetchProjects();
      await get().fetchDashboardStats();
      useToastStore.getState().show('success', 'Project Updated', 'Changes saved successfully.');
    } catch (err: any) {
      useToastStore.getState().show('error', 'Update Failed', err.message);
      throw err;
    }
  },

  deleteProject: async (id: string) => {
    try {
      await api.deleteProject(id);
      await get().fetchProjects();
      await get().fetchDashboardStats();
      useToastStore.getState().show('info', 'Project Deleted', 'Project removed safely from SQLite.');
    } catch (err: any) {
      useToastStore.getState().show('error', 'Deletion Failed', err.message);
      throw err;
    }
  },
}));
