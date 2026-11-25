import React, { useEffect, useState } from 'react';
import {
  FolderKanban,
  Plus,
  Search,
  Grid,
  List as ListIcon,
  MoreVertical,
  Film,
  Scissors,
  Trash2,
  Edit2,
  ExternalLink,
  Calendar,
  AlertTriangle
} from 'lucide-react';
import { useProjectStore } from '../store/projectStore';
import { ProjectData } from '../services/api';
import { Modal } from '../components/ui/Modal';

interface ProjectsPageProps {
  onOpenProject: (projectId: string) => void;
  onNavigateToImport: () => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({
  onOpenProject,
  onNavigateToImport,
}) => {
  const {
    projects,
    searchQuery,
    sortBy,
    sortOrder,
    viewMode,
    isLoading,
    setSearchQuery,
    setSortBy,
    setSortOrder,
    setViewMode,
    fetchProjects,
    createProject,
    updateProject,
    deleteProject,
  } = useProjectStore();

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<ProjectData | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectData | null>(null);

  // Form states
  const [nameInput, setNameInput] = useState('');
  const [descInput, setDescInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nameInput.trim()) return;
    setIsSubmitting(true);
    try {
      await createProject(nameInput.trim(), descInput.trim());
      setIsCreateModalOpen(false);
      setNameInput('');
      setDescInput('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRenameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!renameTarget || !nameInput.trim()) return;
    setIsSubmitting(true);
    try {
      await updateProject(renameTarget.id, nameInput.trim(), descInput.trim());
      setRenameTarget(null);
      setNameInput('');
      setDescInput('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setIsSubmitting(true);
    try {
      await deleteProject(deleteTarget.id);
      setDeleteTarget(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header and Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            <FolderKanban className="w-6 h-6 text-indigo-400" />
            Projects ({projects.length})
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Manage your video repositories, generated clips, and edit decision lists in SQLite.
          </p>
        </div>

        <button
          onClick={() => {
            setNameInput('');
            setDescInput('');
            setIsCreateModalOpen(true);
          }}
          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-600/20 flex items-center gap-2 transition cursor-pointer self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-3 p-3 bg-[#14141d] border border-[#20202e] rounded-2xl">
        <div className="relative w-full md:w-80">
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#1b1b26] border border-[#272738] rounded-xl pl-9 pr-4 py-2 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2.5 w-full md:w-auto justify-between md:justify-end">
          {/* Sort By */}
          <div className="flex items-center gap-1.5 text-xs text-zinc-400">
            <span>Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-[#1b1b26] border border-[#272738] rounded-lg px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none"
            >
              <option value="updated_at">Recently Updated</option>
              <option value="created_at">Date Created</option>
              <option value="name">Project Name</option>
            </select>
          </div>

          {/* Grid vs List toggle */}
          <div className="flex items-center bg-[#1b1b26] p-1 rounded-xl border border-[#272738]">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-lg transition ${
                viewMode === 'grid' ? 'bg-indigo-600 text-white' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <Grid className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-lg transition ${
                viewMode === 'list' ? 'bg-indigo-600 text-white' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <ListIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Projects Listing */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-36 bg-[#14141d] rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="p-12 border-2 border-dashed border-[#20202e] rounded-2xl text-center space-y-3 bg-[#14141d]/30">
          <FolderKanban className="w-10 h-10 text-zinc-600 mx-auto" />
          <h3 className="text-sm font-bold text-white">No projects found</h3>
          <p className="text-xs text-zinc-400 max-w-sm mx-auto">
            {searchQuery
              ? `No projects match "${searchQuery}". Clear your search query to see all projects.`
              : 'Create a project to begin ingesting long videos and generating short clips.'}
          </p>
          {!searchQuery && (
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition cursor-pointer"
            >
              + Create First Project
            </button>
          )}
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {projects.map((proj) => (
            <div
              key={proj.id}
              className="p-5 bg-[#14141d] border border-[#20202e] hover:border-indigo-500/50 rounded-2xl transition space-y-4 flex flex-col justify-between group"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <h3
                    onClick={() => onOpenProject(proj.id)}
                    className="text-base font-extrabold text-white group-hover:text-indigo-400 transition cursor-pointer line-clamp-1"
                  >
                    {proj.name}
                  </h3>

                  <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition">
                    <button
                      onClick={() => {
                        setRenameTarget(proj);
                        setNameInput(proj.name);
                        setDescInput(proj.description || '');
                      }}
                      title="Rename Project"
                      className="p-1 text-zinc-500 hover:text-zinc-200 transition"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setDeleteTarget(proj)}
                      title="Delete Project"
                      className="p-1 text-zinc-500 hover:text-rose-400 transition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <p className="text-xs text-zinc-400 line-clamp-2 min-h-[32px]">
                  {proj.description || 'No description provided.'}
                </p>
              </div>

              <div className="space-y-3 pt-3 border-t border-[#1c1c28]">
                <div className="flex items-center justify-between text-[11px] text-zinc-400">
                  <span className="flex items-center gap-1.5">
                    <Film className="w-3.5 h-3.5 text-zinc-500" />
                    {proj.video_count} videos
                  </span>
                  <span className="flex items-center gap-1.5 text-indigo-400 font-semibold">
                    <Scissors className="w-3.5 h-3.5" />
                    {proj.clip_count} clips
                  </span>
                </div>

                <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                  <span>Updated {new Date(proj.updated_at).toLocaleDateString()}</span>
                  <button
                    onClick={() => onOpenProject(proj.id)}
                    className="text-indigo-400 hover:text-indigo-300 font-bold flex items-center gap-1 cursor-pointer"
                  >
                    Open
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* List View */
        <div className="bg-[#14141d] border border-[#20202e] rounded-2xl overflow-hidden divide-y divide-[#1c1c28]">
          {projects.map((proj) => (
            <div
              key={proj.id}
              className="p-4 flex items-center justify-between hover:bg-[#181824] transition gap-4"
            >
              <div className="flex-1 space-y-0.5">
                <h4
                  onClick={() => onOpenProject(proj.id)}
                  className="text-sm font-bold text-white hover:text-indigo-400 transition cursor-pointer"
                >
                  {proj.name}
                </h4>
                <p className="text-xs text-zinc-400 truncate max-w-lg">{proj.description || 'No description'}</p>
              </div>

              <div className="flex items-center gap-6 text-xs text-zinc-400">
                <span>{proj.video_count} videos</span>
                <span className="text-indigo-400 font-semibold">{proj.clip_count} clips</span>
                <span className="text-[11px] font-mono text-zinc-500">
                  {new Date(proj.updated_at).toLocaleDateString()}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => {
                      setRenameTarget(proj);
                      setNameInput(proj.name);
                      setDescInput(proj.description || '');
                    }}
                    className="p-1.5 text-zinc-400 hover:text-white"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setDeleteTarget(proj)}
                    className="p-1.5 text-zinc-400 hover:text-rose-400"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create Project"
        description="Initialize a new project record in the local SQLite database."
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-300">Project Name</label>
            <input
              type="text"
              required
              placeholder="e.g. AI Strategy Briefing"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              className="w-full bg-[#1b1b26] border border-[#272738] focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-zinc-500 focus:outline-none"
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-300">Description</label>
            <textarea
              placeholder="Project notes, target social channels, or topics..."
              value={descInput}
              onChange={(e) => setDescInput(e.target.value)}
              className="w-full bg-[#1b1b26] border border-[#272738] focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-zinc-500 focus:outline-none h-20 resize-none"
            />
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={() => setIsCreateModalOpen(false)}
              className="px-4 py-2 bg-[#1f1f2e] hover:bg-[#272738] text-xs font-semibold rounded-xl text-zinc-300 transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !nameInput.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold rounded-xl text-white shadow-lg shadow-indigo-600/20 transition cursor-pointer"
            >
              {isSubmitting ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Rename Modal */}
      <Modal
        isOpen={renameTarget !== null}
        onClose={() => setRenameTarget(null)}
        title="Rename Project"
        description="Update project name and details in SQLite."
      >
        <form onSubmit={handleRenameSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-300">Project Name</label>
            <input
              type="text"
              required
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              className="w-full bg-[#1b1b26] border border-[#272738] focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none"
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-300">Description</label>
            <textarea
              value={descInput}
              onChange={(e) => setDescInput(e.target.value)}
              className="w-full bg-[#1b1b26] border border-[#272738] focus:border-indigo-500 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none h-20 resize-none"
            />
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={() => setRenameTarget(null)}
              className="px-4 py-2 bg-[#1f1f2e] hover:bg-[#272738] text-xs font-semibold rounded-xl text-zinc-300 transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !nameInput.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-bold rounded-xl text-white shadow-lg shadow-indigo-600/20 transition cursor-pointer"
            >
              {isSubmitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Project?"
        description="This will safely delete this project and its generated clip records from SQLite."
      >
        <div className="space-y-4">
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-start gap-2.5">
            <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-rose-300 leading-relaxed">
              <strong className="block text-white">Safe Deletion Guarantee:</strong>
              Original source video files on your computer will <strong>never</strong> be deleted.
            </div>
          </div>

          <p className="text-xs text-zinc-400">
            Are you sure you want to delete <span className="text-white font-bold font-mono">"{deleteTarget?.name}"</span>?
          </p>

          <div className="flex justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={() => setDeleteTarget(null)}
              className="px-4 py-2 bg-[#1f1f2e] hover:bg-[#272738] text-xs font-semibold rounded-xl text-zinc-300 transition cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDeleteConfirm}
              disabled={isSubmitting}
              className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-xs font-bold rounded-xl text-white shadow-lg shadow-rose-600/20 transition cursor-pointer"
            >
              {isSubmitting ? 'Deleting...' : 'Delete Project'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
