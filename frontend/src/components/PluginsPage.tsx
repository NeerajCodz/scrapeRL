import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Package,
  Download,
  Trash2,
  Search,
  Filter,
  CheckCircle,
  AlertCircle,
  Loader2,
  Plug,
  Cpu,
  Wrench,
  Database,
  Sparkles,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { classNames } from '@/utils/helpers';

interface Plugin {
  id: string;
  name: string;
  category: string;
  description: string;
  version: string;
  size: string;
  installed: boolean;
  requires_key: boolean;
}

interface PluginsResponse {
  plugins: Record<string, Plugin[]>;
  categories: string[];
  stats: {
    total: number;
    installed: number;
    available: number;
  };
}

interface PluginsPageProps {
  className?: string;
}

const getCategoryIcon = (category: string) => {
  switch (category) {
    case 'apis':
      return <Plug className="w-5 h-5 text-cyan-400" />;
    case 'mcps':
      return <Wrench className="w-5 h-5 text-amber-400" />;
    case 'skills':
      return <Cpu className="w-5 h-5 text-purple-400" />;
    case 'processors':
      return <Database className="w-5 h-5 text-pink-400" />;
    default:
      return <Package className="w-5 h-5 text-gray-400" />;
  }
};

const getCategoryLabel = (category: string) => {
  const labels: Record<string, string> = {
    apis: 'API Providers',
    mcps: 'MCP Tools',
    skills: 'Skills & Agents',
    processors: 'Data Processors',
  };
  return labels[category] || category;
};

const getCategoryColor = (category: string) => {
  const colors: Record<string, string> = {
    apis: 'from-cyan-500/20 to-blue-500/10 border-cyan-500/30',
    mcps: 'from-amber-500/20 to-orange-500/10 border-amber-500/30',
    skills: 'from-purple-500/20 to-pink-500/10 border-purple-500/30',
    processors: 'from-pink-500/20 to-rose-500/10 border-pink-500/30',
  };
  return colors[category] || 'from-gray-500/20 to-gray-500/10 border-gray-500/30';
};

export const PluginsPage: React.FC<PluginsPageProps> = ({ className }) => {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showInstalled, setShowInstalled] = useState(false);

  // Fetch plugins
  const { data: pluginsData, isLoading } = useQuery<PluginsResponse>({
    queryKey: ['plugins'],
    queryFn: async () => {
      const res = await fetch('/api/plugins/');
      return res.json();
    },
  });

  // Install plugin mutation
  const installMutation = useMutation({
    mutationFn: async (pluginId: string) => {
      const res = await fetch('/api/plugins/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin_id: pluginId }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });

  // Uninstall plugin mutation
  const uninstallMutation = useMutation({
    mutationFn: async (pluginId: string) => {
      const res = await fetch('/api/plugins/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin_id: pluginId }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail);
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });

  // Filter plugins
  const getFilteredPlugins = () => {
    if (!pluginsData?.plugins) return {};

    const result: Record<string, Plugin[]> = {};

    for (const [category, plugins] of Object.entries(pluginsData.plugins)) {
      if (selectedCategory && category !== selectedCategory) continue;

      const filtered = plugins.filter((plugin) => {
        const matchesSearch =
          !searchQuery ||
          plugin.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          plugin.description.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesInstalled = !showInstalled || plugin.installed;

        return matchesSearch && matchesInstalled;
      });

      if (filtered.length > 0) {
        result[category] = filtered;
      }
    }

    return result;
  };

  const filteredPlugins = getFilteredPlugins();

  return (
    <div className={classNames('space-y-6', className)}>
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-lg">
              <Package className="w-6 h-6 text-cyan-400" />
            </div>
            Plugins
          </h1>
          <p className="text-gray-400 mt-1">
            Extend ScrapeRL with APIs, tools, skills, and processors
          </p>
        </div>
        
        {/* Stats */}
        {pluginsData?.stats && (
          <div className="flex gap-4">
            <div className="px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-center">
              <div className="text-xl font-bold text-emerald-400">
                {pluginsData.stats.installed}
              </div>
              <div className="text-xs text-emerald-400/70">Installed</div>
            </div>
            <div className="px-4 py-2 bg-gray-700/30 border border-gray-600/30 rounded-xl text-center">
              <div className="text-xl font-bold text-gray-300">
                {pluginsData.stats.available}
              </div>
              <div className="text-xs text-gray-500">Available</div>
            </div>
            <div className="px-4 py-2 bg-purple-500/10 border border-purple-500/30 rounded-xl text-center">
              <div className="text-xl font-bold text-purple-400">
                {pluginsData.stats.total}
              </div>
              <div className="text-xs text-purple-400/70">Total</div>
            </div>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
        <div className="flex flex-wrap gap-4 items-center">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                placeholder="Search plugins..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
              />
            </div>
          </div>

          {/* Category Filter */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setSelectedCategory(null)}
              className={classNames(
                'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                selectedCategory === null
                  ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                  : 'bg-gray-700/50 text-gray-400 hover:text-gray-200 hover:bg-gray-700'
              )}
            >
              All
            </button>
            {['apis', 'mcps', 'skills', 'processors'].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={classNames(
                  'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                  selectedCategory === cat
                    ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                    : 'bg-gray-700/50 text-gray-400 hover:text-gray-200 hover:bg-gray-700'
                )}
              >
                {getCategoryIcon(cat)}
                {getCategoryLabel(cat)}
              </button>
            ))}
          </div>

          {/* Show Installed Toggle */}
          <button
            onClick={() => setShowInstalled(!showInstalled)}
            className={classNames(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
              showInstalled
                ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/20'
                : 'bg-gray-700/50 text-gray-400 hover:text-gray-200 hover:bg-gray-700'
            )}
          >
            <Filter className="w-4 h-4" />
            Installed Only
          </button>
        </div>
      </div>

      {/* Plugin List */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="w-10 h-10 text-cyan-400 animate-spin mb-4" />
          <p className="text-gray-400">Loading plugins...</p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(filteredPlugins).map(([category, plugins]) => (
            <div key={category}>
              <div className="flex items-center gap-3 mb-4">
                <div className={`p-2 rounded-lg bg-gradient-to-br ${getCategoryColor(category)}`}>
                  {getCategoryIcon(category)}
                </div>
                <h2 className="text-lg font-semibold text-white">
                  {getCategoryLabel(category)}
                </h2>
                <Badge variant="neutral" size="sm">
                  {plugins.length}
                </Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {plugins.map((plugin) => (
                  <div
                    key={plugin.id}
                    className={`relative bg-gradient-to-br ${getCategoryColor(category)} border rounded-xl p-5 backdrop-blur-sm transition-all hover:scale-[1.02] hover:shadow-xl`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-white">{plugin.name}</h3>
                        {plugin.installed && (
                          <CheckCircle className="w-4 h-4 text-emerald-400" />
                        )}
                      </div>
                      <Badge 
                        variant={plugin.installed ? 'success' : 'neutral'} 
                        size="sm"
                      >
                        {plugin.installed ? 'Installed' : 'Available'}
                      </Badge>
                    </div>
                    
                    <p className="text-sm text-gray-400 mb-4 line-clamp-2">
                      {plugin.description}
                    </p>
                    
                    <div className="flex items-center gap-3 text-xs text-gray-500 mb-4">
                      <span className="px-2 py-0.5 bg-gray-800/50 rounded">v{plugin.version}</span>
                      <span>{plugin.size}</span>
                      {plugin.requires_key && (
                        <span className="flex items-center gap-1 text-amber-400">
                          <Sparkles className="w-3 h-3" />
                          API Key
                        </span>
                      )}
                    </div>

                    {plugin.installed ? (
                      <button
                        onClick={() => uninstallMutation.mutate(plugin.id)}
                        disabled={uninstallMutation.isPending}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 rounded-lg font-medium transition-all disabled:opacity-50"
                      >
                        <Trash2 className="w-4 h-4" />
                        Uninstall
                      </button>
                    ) : (
                      <button
                        onClick={() => installMutation.mutate(plugin.id)}
                        disabled={installMutation.isPending}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                      >
                        <Download className="w-4 h-4" />
                        Install
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}

          {Object.keys(filteredPlugins).length === 0 && (
            <div className="text-center py-16">
              <div className="w-16 h-16 bg-gray-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Package className="w-8 h-8 text-gray-500" />
              </div>
              <h3 className="text-lg font-medium text-gray-300">No plugins found</h3>
              <p className="text-gray-500 mt-1">
                Try adjusting your search or filter criteria
              </p>
            </div>
          )}
        </div>
      )}

      {/* Error Messages */}
      {uninstallMutation.isError && (
        <div className="fixed bottom-4 right-4 flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl backdrop-blur-sm shadow-xl">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <span className="text-sm text-red-400">
            {(uninstallMutation.error as Error).message}
          </span>
        </div>
      )}
    </div>
  );
};

export default PluginsPage;
