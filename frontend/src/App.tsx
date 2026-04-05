import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Home, Settings as SettingsIcon, Package, Zap, Brain, Github, Book, Cpu } from 'lucide-react';
import Dashboard from './components/Dashboard';
import Settings from './components/Settings';
import PluginsPage from './components/PluginsPage';
import DocsPage from './components/DocsPage';
import AgentsPage from './components/AgentsPage';
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
    { path: '/agents', label: 'Agents', icon: Cpu },
    { path: '/plugins', label: 'Plugins', icon: Package },
    { path: '/docs', label: 'Docs', icon: Book },
    { path: '/settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <nav className="bg-gradient-to-r from-navy-900 via-navy-800 to-navy-900 border-b border-cyan-900/30 shadow-lg shadow-cyan-500/10">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-9 h-9 bg-gradient-to-br from-cyan-500 via-cyan-600 to-cyan-700 rounded-lg flex items-center justify-center shadow-lg shadow-cyan-500/40">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-cyan-400 rounded-full animate-pulse shadow-lg shadow-cyan-400/50" />
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-bold bg-gradient-to-r from-cyan-400 via-cyan-300 to-cyan-500 bg-clip-text text-transparent">
                ScrapeRL
              </span>
              <span className="text-[9px] text-cyan-600 font-medium tracking-wider -mt-0.5">
                RL-POWERED SCRAPING
              </span>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex items-center gap-1">
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className={classNames(
                  'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
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
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-gray-100 flex flex-col">
          <NavBar />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/agents" element={<AgentsPage className="p-6" />} />
              <Route path="/plugins" element={<PluginsPage className="p-6" />} />
              <Route path="/docs" element={<DocsPage />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
