import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Home, Settings as SettingsIcon, Package, Activity, Zap, Brain, Github } from 'lucide-react';
import Dashboard from './components/Dashboard';
import Settings from './components/Settings';
import PluginsPage from './components/PluginsPage';
import { classNames } from './utils/helpers';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
});

function NavBar() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Home },
    { path: '/plugins', label: 'Plugins', icon: Package },
    { path: '/settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <nav className="bg-gradient-to-r from-gray-900 via-gray-900 to-gray-800 border-b border-gray-700/50 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full animate-pulse" />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
                ScrapeRL
              </span>
              <span className="text-[10px] text-gray-500 font-medium tracking-wider">
                RL-POWERED SCRAPING
              </span>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex items-center gap-2">
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className={classNames(
                  'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                  location.pathname === path
                    ? 'bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 text-emerald-400 shadow-lg shadow-emerald-500/10 border border-emerald-500/30'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                )}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            ))}
          </div>

          {/* Status Badge */}
          <div className="hidden md:flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-full">
              <Zap className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-xs text-emerald-400 font-medium">Online</span>
            </div>
            <a
              href="https://github.com/NeerajCodz/scrapeRL"
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 text-gray-500 hover:text-gray-300 transition-colors"
            >
              <Github className="w-5 h-5" />
            </a>
          </div>
        </div>
      </div>
    </nav>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-gray-100">
          <NavBar />
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/plugins" element={<PluginsPage />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
          
          {/* Footer */}
          <footer className="border-t border-gray-800/50 bg-gray-900/30">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-gray-500">
                <div className="flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5 text-emerald-500" />
                  <span>ScrapeRL v0.1.0 • Reinforcement Learning Web Scraping</span>
                </div>
                <div className="flex items-center gap-4">
                  <span>Built with FastAPI + React</span>
                  <a 
                    href="https://huggingface.co/spaces/NeerajCodz/scrapeRL" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-cyan-500 hover:text-cyan-400 transition-colors"
                  >
                    🤗 HuggingFace
                  </a>
                </div>
              </div>
            </div>
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
