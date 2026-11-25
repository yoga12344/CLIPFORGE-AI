import React, { useState } from 'react';
import { AppLayout, NavItem } from './components/layout/AppLayout';
import { Dashboard } from './pages/Dashboard';
import { ProjectsPage } from './pages/Projects';
import { ProjectStudio } from './pages/ProjectStudio';
import { VideoImport } from './pages/VideoImport';
import { VideoLibraryPage } from './pages/VideoLibraryPage';
import { CompositionStudioPage } from './pages/CompositionStudioPage';
import { SubtitleTemplatesPage } from './pages/SubtitleTemplatesPage';
import { ExportCenterPage } from './pages/ExportCenterPage';
import { ModelManagerPage } from './pages/ModelManagerPage';
import { JobQueuePage } from './pages/JobQueuePage';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { SettingsPage } from './pages/Settings';
import { ToastContainer } from './components/ui/ToastContainer';

export default function App() {
  const [activeNav, setActiveNav] = useState<NavItem>('dashboard');
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);

  const handleOpenProject = (projectId: string) => {
    setActiveProjectId(projectId);
    setActiveNav('projects');
  };

  const handleImportComplete = (projectId: string, videoId: string) => {
    setActiveProjectId(projectId);
    setActiveNav('projects');
  };

  const renderContent = () => {
    switch (activeNav) {
      case 'dashboard':
        return (
          <Dashboard
            onNavigateToCreate={() => setActiveNav('create')}
            onNavigateToProjects={() => {
              setActiveProjectId(null);
              setActiveNav('projects');
            }}
            onSelectProject={handleOpenProject}
          />
        );
      case 'projects':
        if (activeProjectId) {
          return (
            <ProjectStudio
              projectId={activeProjectId}
              onBack={() => setActiveProjectId(null)}
              onNavigateToImport={() => setActiveNav('create')}
            />
          );
        }
        return (
          <ProjectsPage
            onOpenProject={handleOpenProject}
            onNavigateToImport={() => setActiveNav('create')}
          />
        );
      case 'library':
        return (
          <VideoLibraryPage
            onOpenProject={handleOpenProject}
            onNavigateToImport={() => setActiveNav('create')}
            onNavigateToStudio={() => setActiveNav('studio')}
          />
        );
      case 'create':
        return (
          <VideoImport
            initialProjectId={activeProjectId}
            onImportComplete={handleImportComplete}
          />
        );
      case 'studio':
        return <CompositionStudioPage />;
      case 'templates':
        return <SubtitleTemplatesPage />;
      case 'exports':
        return <ExportCenterPage onNavigateToStudio={() => setActiveNav('studio')} />;
      case 'models':
        return <ModelManagerPage />;
      case 'queue':
        return <JobQueuePage />;
      case 'diagnostics':
        return <DiagnosticsPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return (
          <Dashboard
            onNavigateToCreate={() => setActiveNav('create')}
            onNavigateToProjects={() => {
              setActiveProjectId(null);
              setActiveNav('projects');
            }}
            onSelectProject={handleOpenProject}
          />
        );
    }
  };

  return (
    <AppLayout
      activeNav={activeNav}
      onNavigate={(nav) => {
        if (nav !== 'projects') {
          setActiveProjectId(null);
        }
        setActiveNav(nav);
      }}
    >
      {renderContent()}
      <ToastContainer />
    </AppLayout>
  );
}
