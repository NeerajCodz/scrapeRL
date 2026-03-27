import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Wrench,
  Search,
  ToggleLeft,
  ToggleRight,
  Play,
  ChevronDown,
  ChevronUp,
  Clock,
  Hash,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { apiClient } from '@/api/client';
import { formatTimestamp } from '@/utils/helpers';
import type { MCPTool } from '@/types';

interface ToolRegistryProps {
  className?: string;
}

interface ToolCardProps {
  tool: MCPTool;
  onToggle: (enabled: boolean) => void;
  onExecute: (params: Record<string, unknown>) => void;
  isToggling: boolean;
}

const ToolCard: React.FC<ToolCardProps> = ({
  tool,
  onToggle,
  onExecute,
  isToggling,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const categoryColors: Record<string, string> = {
    browser: 'text-blue-400 bg-blue-400/10',
    extraction: 'text-purple-400 bg-purple-400/10',
    navigation: 'text-green-400 bg-green-400/10',
    validation: 'text-orange-400 bg-orange-400/10',
    utility: 'text-gray-400 bg-gray-400/10',
  };

  return (
    <div className="bg-dark-900/50 rounded-lg overflow-hidden">
      <div className="p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-sm text-dark-100">
                {tool.name}
              </span>
              <Badge
                variant={tool.enabled ? 'success' : 'neutral'}
                size="sm"
              >
                {tool.enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
            <p className="text-xs text-dark-400 line-clamp-2">
              {tool.description}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onToggle(!tool.enabled)}
              disabled={isToggling}
              className="text-dark-400 hover:text-dark-200 transition-colors"
            >
              {tool.enabled ? (
                <ToggleRight className="w-6 h-6 text-accent-primary" />
              ) : (
                <ToggleLeft className="w-6 h-6" />
              )}
            </button>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-dark-400 hover:text-dark-200 transition-colors"
            >
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 mt-2">
          <span
            className={`text-xs px-2 py-0.5 rounded ${
              categoryColors[tool.category] ?? categoryColors.utility
            }`}
          >
            {tool.category}
          </span>
          <div className="flex items-center gap-1 text-xs text-dark-500">
            <Hash className="w-3 h-3" />
            <span>{tool.usageCount}</span>
          </div>
          {tool.lastUsed && (
            <div className="flex items-center gap-1 text-xs text-dark-500">
              <Clock className="w-3 h-3" />
              <span>{formatTimestamp(tool.lastUsed)}</span>
            </div>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 border-t border-dark-700">
          <div className="mt-3">
            <div className="text-xs text-dark-400 mb-2">Input Schema</div>
            <div className="code-block text-xs max-h-40 overflow-y-auto">
              {JSON.stringify(tool.inputSchema, null, 2)}
            </div>
          </div>

          <div className="mt-3 flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onExecute({})}
              disabled={!tool.enabled}
              leftIcon={<Play className="w-3 h-3" />}
            >
              Test Execute
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export const ToolRegistry: React.FC<ToolRegistryProps> = ({ className }) => {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const { data: tools, isLoading } = useQuery({
    queryKey: ['tools'],
    queryFn: () => apiClient.getTools(),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      apiClient.toggleTool(name, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] });
    },
  });

  const executeMutation = useMutation({
    mutationFn: ({
      name,
      params,
    }: {
      name: string;
      params: Record<string, unknown>;
    }) => apiClient.executeTool(name, params),
  });

  const categories = React.useMemo((): string[] => {
    if (!tools) return [];
    return [...new Set(tools.map((t) => t.category).filter((c): c is string => !!c))];
  }, [tools]);

  const filteredTools = React.useMemo(() => {
    if (!tools) return [];
    return tools.filter((tool) => {
      const matchesSearch =
        !searchQuery ||
        tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory =
        !categoryFilter || tool.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [tools, searchQuery, categoryFilter]);

  const enabledCount = tools?.filter((t) => t.enabled).length ?? 0;

  return (
    <Card className={className}>
      <CardHeader
        title="MCP Tools"
        subtitle={`${enabledCount}/${tools?.length ?? 0} enabled`}
        icon={<Wrench className="w-4 h-4" />}
      />
      <CardContent>
        {/* Search & Filter */}
        <div className="flex gap-2 mb-4">
          <Input
            placeholder="Search tools..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-4 h-4" />}
            className="flex-1"
          />
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setCategoryFilter(null)}
            className={`px-3 py-1 text-xs rounded-full transition-colors ${
              !categoryFilter
                ? 'bg-accent-primary text-white'
                : 'bg-dark-700 text-dark-300 hover:bg-dark-600'
            }`}
          >
            All
          </button>
          {categories.map((cat: string) => (
            <button
              key={cat}
              onClick={() =>
                setCategoryFilter(categoryFilter === cat ? null : cat)
              }
              className={`px-3 py-1 text-xs rounded-full transition-colors capitalize ${
                categoryFilter === cat
                  ? 'bg-accent-primary text-white'
                  : 'bg-dark-700 text-dark-300 hover:bg-dark-600'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Tools List */}
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Wrench className="w-6 h-6 text-dark-500 animate-pulse" />
            </div>
          ) : filteredTools.length === 0 ? (
            <div className="text-center py-8 text-dark-500">
              <Wrench className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No tools found</p>
            </div>
          ) : (
            filteredTools.map((tool) => (
              <ToolCard
                key={tool.name}
                tool={tool}
                onToggle={(enabled) =>
                  toggleMutation.mutate({ name: tool.name, enabled })
                }
                onExecute={(params) =>
                  executeMutation.mutate({ name: tool.name, params })
                }
                isToggling={toggleMutation.isPending}
              />
            ))
          )}
        </div>

        {/* Execution Result */}
        {executeMutation.data !== undefined && (
          <div className="mt-4 p-3 bg-dark-900/50 rounded-lg">
            <div className="text-xs text-dark-400 mb-1">Execution Result</div>
            <div className="code-block text-xs max-h-32 overflow-y-auto">
              {JSON.stringify(executeMutation.data, null, 2)}
            </div>
          </div>
        )}

        {executeMutation.isError && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="text-xs text-red-400">
              {(executeMutation.error as Error).message}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ToolRegistry;
