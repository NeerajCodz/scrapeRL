import React, { useState } from 'react';
import {
  LayoutDashboard,
  Settings as SettingsIcon,
  Activity,
  Menu,
  X,
  Wifi,
  WifiOff,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { EpisodePanel } from './EpisodePanel';
import { AgentView } from './AgentView';
import { MemoryPanel } from './MemoryPanel';
import { ToolRegistry } from './ToolRegistry';
import { RewardChart } from './RewardChart';
import { ObservationView } from './ObservationView';
import { ActionPanel } from './ActionPanel';
import { Settings } from './Settings';
import { Badge } from '@/components/ui/Badge';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useCurrentEpisode } from '@/hooks/useEpisode';

type ViewMode = 'dashboard' | 'settings';

export const Dashboard: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const { isConnected, isConnecting } = useWebSocket('/ws', {
    onMessage: (message) => {
      console.log('WebSocket message:', message);
    },
  });

  const { data: episode } = useCurrentEpisode();

  return (
    <div className="min-h-screen bg-dark-900 flex">
      {/* Sidebar */}
      <aside
        className={`fixed lg:relative inset-y-0 left-0 z-40 bg-dark-800 border-r border-dark-700 
          transition-all duration-300 ${
            sidebarCollapsed ? 'w-16' : 'w-64'
          } ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-dark-700">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-accent-primary to-accent-tertiary rounded-lg flex items-center justify-center">
                <Activity className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-lg gradient-text">ScrapeRL</span>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="hidden lg:flex p-1.5 text-dark-400 hover:text-dark-200 hover:bg-dark-700 rounded transition-colors"
          >
            {sidebarCollapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="lg:hidden p-1.5 text-dark-400 hover:text-dark-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="p-2 space-y-1">
          <button
            onClick={() => {
              setViewMode('dashboard');
              setMobileMenuOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
              viewMode === 'dashboard'
                ? 'bg-accent-primary/10 text-accent-primary'
                : 'text-dark-400 hover:text-dark-200 hover:bg-dark-700'
            }`}
          >
            <LayoutDashboard className="w-5 h-5 flex-shrink-0" />
            {!sidebarCollapsed && <span>Dashboard</span>}
          </button>
          <button
            onClick={() => {
              setViewMode('settings');
              setMobileMenuOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
              viewMode === 'settings'
                ? 'bg-accent-primary/10 text-accent-primary'
                : 'text-dark-400 hover:text-dark-200 hover:bg-dark-700'
            }`}
          >
            <SettingsIcon className="w-5 h-5 flex-shrink-0" />
            {!sidebarCollapsed && <span>Settings</span>}
          </button>
        </nav>

        {/* Status */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-dark-700">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Wifi className="w-4 h-4 text-green-400" />
            ) : isConnecting ? (
              <Wifi className="w-4 h-4 text-yellow-400 animate-pulse" />
            ) : (
              <WifiOff className="w-4 h-4 text-red-400" />
            )}
            {!sidebarCollapsed && (
              <span className="text-xs text-dark-400">
                {isConnected
                  ? 'Connected'
                  : isConnecting
                  ? 'Connecting...'
                  : 'Disconnected'}
              </span>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-dark-800 border-b border-dark-700 flex items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 text-dark-400 hover:text-dark-200"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-semibold text-dark-100">
                {viewMode === 'dashboard' ? 'Dashboard' : 'Settings'}
              </h1>
              {episode && (
                <p className="text-xs text-dark-400">
                  Episode: {episode.id.slice(0, 8)}...
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {episode && (
              <Badge
                variant={
                  episode.status === 'running'
                    ? 'success'
                    : episode.status === 'failed'
                    ? 'error'
                    : 'neutral'
                }
                dot
                pulse={episode.status === 'running'}
              >
                {episode.status}
              </Badge>
            )}
          </div>
        </header>

        {/* Content Area */}
        <div className="h-[calc(100vh-4rem)] overflow-auto p-4 lg:p-6">
          {viewMode === 'dashboard' ? (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6">
              {/* Left Column */}
              <div className="lg:col-span-3 space-y-4 lg:space-y-6">
                <EpisodePanel />
                <AgentView />
              </div>

              {/* Center Column */}
              <div className="lg:col-span-6 space-y-4 lg:space-y-6">
                <ObservationView />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
                  <RewardChart />
                  <ActionPanel />
                </div>
              </div>

              {/* Right Column */}
              <div className="lg:col-span-3 space-y-4 lg:space-y-6">
                <MemoryPanel />
                <ToolRegistry />
              </div>
            </div>
          ) : (
            <div className="max-w-2xl mx-auto">
              <Settings />
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
