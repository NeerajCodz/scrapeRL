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
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
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

interface Category {
  id: string;
  name: string;
  description: string;
  icon: string;
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
      return <Plug className="w-5 h-5" />;
    case 'mcps':
      return <Wrench className="w-5 h-5" />;
    case 'skills':
      return <Cpu className="w-5 h-5" />;
    case 'processors':
      return <Database className="w-5 h-5" />;
    default:
      return <Package className="w-5 h-5" />;
  }
};

const getCategoryLabel = (category: string) => {
  const labels: Record<string, string> = {
    apis: 'API Providers',
    mcps: 'MCP Tools',
    skills: 'Skills/Agents',
    processors: 'Data Processors',
  };
  return labels[category] || category;
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

  // Fetch categories
  const { data: categoriesData } = useQuery<{ categories: Category[] }>({
    queryKey: ['plugin-categories'],
    queryFn: async () => {
      const res = await fetch('/api/plugins/categories');
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-100">Plugins</h1>
          <p className="text-dark-400 mt-1">
            Extend ScrapeRL with APIs, tools, skills, and processors
          </p>
        </div>
        {pluginsData?.stats && (
          <div className="flex gap-4 text-sm">
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-400">
                {pluginsData.stats.installed}
              </div>
              <div className="text-dark-400">Installed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-dark-300">
                {pluginsData.stats.available}
              </div>
              <div className="text-dark-400">Available</div>
            </div>
          </div>
        )}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4 items-center">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <Input
                placeholder="Search plugins..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                leftIcon={<Search className="w-4 h-4" />}
              />
            </div>

            {/* Category Filter */}
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={selectedCategory === null ? 'primary' : 'ghost'}
                onClick={() => setSelectedCategory(null)}
              >
                All
              </Button>
              {categoriesData?.categories.map((cat) => (
                <Button
                  key={cat.id}
                  size="sm"
                  variant={selectedCategory === cat.id ? 'primary' : 'ghost'}
                  onClick={() => setSelectedCategory(cat.id)}
                  leftIcon={<span>{cat.icon}</span>}
                >
                  {cat.name}
                </Button>
              ))}
            </div>

            {/* Show Installed Toggle */}
            <Button
              size="sm"
              variant={showInstalled ? 'primary' : 'ghost'}
              onClick={() => setShowInstalled(!showInstalled)}
              leftIcon={<Filter className="w-4 h-4" />}
            >
              Installed Only
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Plugin List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(filteredPlugins).map(([category, plugins]) => (
            <div key={category}>
              <div className="flex items-center gap-2 mb-4">
                {getCategoryIcon(category)}
                <h2 className="text-lg font-semibold text-dark-100">
                  {getCategoryLabel(category)}
                </h2>
                <Badge variant="neutral" size="sm">
                  {plugins.length}
                </Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {plugins.map((plugin) => (
                  <Card key={plugin.id} className="relative">
                    <CardContent className="py-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium text-dark-100">
                              {plugin.name}
                            </h3>
                            {plugin.installed && (
                              <CheckCircle className="w-4 h-4 text-green-400" />
                            )}
                          </div>
                          <p className="text-sm text-dark-400 mt-1">
                            {plugin.description}
                          </p>
                          <div className="flex items-center gap-3 mt-3 text-xs text-dark-500">
                            <span>v{plugin.version}</span>
                            <span>•</span>
                            <span>{plugin.size}</span>
                            {plugin.requires_key && (
                              <>
                                <span>•</span>
                                <span className="text-yellow-400">
                                  Requires API Key
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-2 mt-4">
                        {plugin.installed ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="flex-1 text-red-400 hover:text-red-300"
                            onClick={() => uninstallMutation.mutate(plugin.id)}
                            disabled={uninstallMutation.isPending}
                            leftIcon={<Trash2 className="w-4 h-4" />}
                          >
                            Uninstall
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="primary"
                            className="flex-1"
                            onClick={() => installMutation.mutate(plugin.id)}
                            disabled={installMutation.isPending}
                            leftIcon={<Download className="w-4 h-4" />}
                          >
                            Install
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}

          {Object.keys(filteredPlugins).length === 0 && (
            <div className="text-center py-12">
              <Package className="w-12 h-12 text-dark-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-dark-300">No plugins found</h3>
              <p className="text-dark-400 mt-1">
                Try adjusting your search or filter criteria
              </p>
            </div>
          )}
        </div>
      )}

      {/* Error Messages */}
      {uninstallMutation.isError && (
        <div className="fixed bottom-4 right-4 flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
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
