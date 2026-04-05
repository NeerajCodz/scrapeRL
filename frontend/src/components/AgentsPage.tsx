import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bot,
  Cpu,
  Download,
  Loader2,
  Search,
  Shield,
  Trash2,
  Users,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { classNames } from '@/utils/helpers';

interface AgentModule {
  id: string;
  name: string;
  role: string;
  description: string;
  version: string;
  installed: boolean;
  default: boolean;
  orchestrator_compatible: boolean;
}

interface AgentCatalogResponse {
  agents: AgentModule[];
  stats: {
    total: number;
    installed: number;
    available: number;
  };
}

interface AgentsPageProps {
  className?: string;
}

const roleIcon = (role: string) => {
  if (role.includes('coordinator')) return <Users className="w-5 h-5 text-cyan-400" />;
  if (role.includes('memory')) return <Shield className="w-5 h-5 text-emerald-400" />;
  return <Bot className="w-5 h-5 text-purple-400" />;
};

const roleLabel = (role: string) => role.replace('-', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export const AgentsPage: React.FC<AgentsPageProps> = ({ className }) => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [installedOnly, setInstalledOnly] = useState(false);

  const { data, isLoading } = useQuery<AgentCatalogResponse>({
    queryKey: ['agent-catalog'],
    queryFn: async () => {
      const res = await fetch('/api/agents/catalog');
      return res.json();
    },
  });

  const installMutation = useMutation({
    mutationFn: async (agentId: string) => {
      const res = await fetch('/api/agents/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Install failed');
      }
      return res.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agent-catalog'] }),
  });

  const uninstallMutation = useMutation({
    mutationFn: async (agentId: string) => {
      const res = await fetch('/api/agents/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Uninstall failed');
      }
      return res.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agent-catalog'] }),
  });

  const filtered = useMemo(() => {
    const agents = data?.agents ?? [];
    return agents.filter((agent) => {
      const matchesInstalled = !installedOnly || agent.installed;
      const q = search.trim().toLowerCase();
      const matchesSearch =
        !q ||
        agent.name.toLowerCase().includes(q) ||
        agent.role.toLowerCase().includes(q) ||
        agent.description.toLowerCase().includes(q);
      return matchesInstalled && matchesSearch;
    });
  }, [data?.agents, installedOnly, search]);

  return (
    <div className={classNames('space-y-6 p-6', className)}>
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-purple-500/20 to-cyan-500/20 rounded-lg">
              <Cpu className="w-6 h-6 text-purple-300" />
            </div>
            Agents
          </h1>
          <p className="text-gray-400 mt-1">
            Browse and install orchestrator-compatible scraper agents
          </p>
        </div>

        {data?.stats && (
          <div className="flex gap-3">
            <div className="px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-center">
              <div className="text-xl font-bold text-emerald-400">{data.stats.installed}</div>
              <div className="text-xs text-emerald-400/70">Installed</div>
            </div>
            <div className="px-4 py-2 bg-gray-700/30 border border-gray-600/30 rounded-xl text-center">
              <div className="text-xl font-bold text-gray-300">{data.stats.available}</div>
              <div className="text-xs text-gray-500">Available</div>
            </div>
            <div className="px-4 py-2 bg-purple-500/10 border border-purple-500/30 rounded-xl text-center">
              <div className="text-xl font-bold text-purple-300">{data.stats.total}</div>
              <div className="text-xs text-purple-300/70">Total</div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex-1 min-w-[240px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                placeholder="Search agents..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
              />
            </div>
          </div>
          <button
            onClick={() => setInstalledOnly((v) => !v)}
            className={classNames(
              'px-4 py-2 rounded-lg text-sm font-medium transition-all',
              installedOnly
                ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/20'
                : 'bg-gray-700/50 text-gray-400 hover:text-gray-200 hover:bg-gray-700'
            )}
          >
            Installed Only
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="w-10 h-10 text-cyan-400 animate-spin mb-4" />
          <p className="text-gray-400">Loading agents...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((agent) => (
            <div
              key={agent.id}
              className="relative bg-gradient-to-br from-gray-800/70 to-gray-900/50 border border-gray-700/70 rounded-xl p-5 backdrop-blur-sm transition-all hover:scale-[1.01] hover:shadow-xl"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  {roleIcon(agent.role)}
                  <h3 className="font-semibold text-white">{agent.name}</h3>
                  {agent.installed && <CheckCircle className="w-4 h-4 text-emerald-400" />}
                </div>
                <Badge variant={agent.installed ? 'success' : 'neutral'} size="sm">
                  {agent.installed ? 'Installed' : 'Available'}
                </Badge>
              </div>

              <p className="text-sm text-gray-400 mb-4 line-clamp-3">{agent.description}</p>

              <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500 mb-4">
                <span className="px-2 py-0.5 bg-gray-800/50 rounded">v{agent.version}</span>
                <span className="px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/30 rounded text-cyan-300">
                  {roleLabel(agent.role)}
                </span>
                {agent.default && (
                  <span className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/30 rounded text-amber-300">
                    Default
                  </span>
                )}
                {agent.orchestrator_compatible && (
                  <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-emerald-300">
                    Orchestrator
                  </span>
                )}
              </div>

              {agent.installed ? (
                <button
                  onClick={() => uninstallMutation.mutate(agent.id)}
                  disabled={uninstallMutation.isPending || agent.default}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Trash2 className="w-4 h-4" />
                  {agent.default ? 'Default Agent' : 'Uninstall'}
                </button>
              ) : (
                <button
                  onClick={() => installMutation.mutate(agent.id)}
                  disabled={installMutation.isPending}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                >
                  <Download className="w-4 h-4" />
                  Install
                </button>
              )}
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="col-span-full text-center py-16">
              <div className="w-16 h-16 bg-gray-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Cpu className="w-8 h-8 text-gray-500" />
              </div>
              <h3 className="text-lg font-medium text-gray-300">No agents found</h3>
              <p className="text-gray-500 mt-1">Try changing search or installed filter</p>
            </div>
          )}
        </div>
      )}

      {(installMutation.isError || uninstallMutation.isError) && (
        <div className="fixed bottom-4 right-4 flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl backdrop-blur-sm shadow-xl">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <span className="text-sm text-red-400">
            {(installMutation.error as Error)?.message ||
              (uninstallMutation.error as Error)?.message ||
              'Agent action failed'}
          </span>
        </div>
      )}
    </div>
  );
};

export default AgentsPage;

