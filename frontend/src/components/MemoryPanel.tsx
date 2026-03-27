import React, { useState } from 'react';
import {
  Database,
  Search,
  Trash2,
  Clock,
  Layers,
  Archive,
  Share2,
  AlertCircle,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import {
  useMemory,
  useClearMemory,
  useQueryMemory,
  getMemoryLayerBadge,
  formatMemorySize,
} from '@/hooks/useMemory';
import { useCurrentEpisode } from '@/hooks/useEpisode';
import { formatTimestamp, truncateText } from '@/utils/helpers';
import type { MemoryEntry, MemoryLayer } from '@/types';

interface MemoryPanelProps {
  className?: string;
}

const MEMORY_TABS: { key: MemoryLayer; label: string; icon: React.ReactNode }[] = [
  { key: 'short_term', label: 'Short-Term', icon: <Clock className="w-3 h-3" /> },
  { key: 'working', label: 'Working', icon: <Layers className="w-3 h-3" /> },
  { key: 'long_term', label: 'Long-Term', icon: <Archive className="w-3 h-3" /> },
  { key: 'shared', label: 'Shared', icon: <Share2 className="w-3 h-3" /> },
];

const MemoryEntryCard: React.FC<{ entry: MemoryEntry }> = ({ entry }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className="p-2 bg-dark-900/50 rounded-lg hover:bg-dark-900/70 transition-colors cursor-pointer"
      onClick={() => setIsExpanded(!isExpanded)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="neutral" size="sm">
              {entry.type}
            </Badge>
            <div
              className="h-1.5 w-8 rounded-full bg-dark-700 overflow-hidden"
              title={`Importance: ${(entry.importance * 100).toFixed(0)}%`}
            >
              <div
                className="h-full bg-accent-primary"
                style={{ width: `${entry.importance * 100}%` }}
              />
            </div>
          </div>
          <p className="text-sm text-dark-200">
            {isExpanded ? entry.content : truncateText(entry.content, 80)}
          </p>
        </div>
        <span className="text-xs text-dark-500 whitespace-nowrap">
          {formatTimestamp(entry.timestamp)}
        </span>
      </div>
      {isExpanded && entry.metadata && Object.keys(entry.metadata).length > 0 && (
        <div className="mt-2 pt-2 border-t border-dark-700">
          <div className="text-xs text-dark-500 font-mono">
            {JSON.stringify(entry.metadata, null, 2)}
          </div>
        </div>
      )}
    </div>
  );
};

export const MemoryPanel: React.FC<MemoryPanelProps> = ({ className }) => {
  const { data: episode } = useCurrentEpisode();
  const { data: memory, isLoading } = useMemory(episode?.id);
  const clearMemoryMutation = useClearMemory(episode?.id);
  const queryMemoryMutation = useQueryMemory(episode?.id);

  const [activeTab, setActiveTab] = useState<MemoryLayer>('working');
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = () => {
    if (searchQuery.trim() && episode?.id) {
      queryMemoryMutation.mutate({
        query: searchQuery,
        layer: activeTab,
        limit: 10,
      });
    }
  };

  const handleClear = () => {
    if (episode?.id && confirm(`Clear all ${activeTab.replace('_', ' ')} memory?`)) {
      clearMemoryMutation.mutate(activeTab);
    }
  };

  const getEntriesForTab = (): MemoryEntry[] => {
    if (!memory) return [];
    switch (activeTab) {
      case 'short_term':
        return memory.shortTerm;
      case 'working':
        return memory.working;
      case 'long_term':
        return memory.longTerm;
      case 'shared':
        return memory.shared;
      default:
        return [];
    }
  };

  const entries = queryMemoryMutation.data ?? getEntriesForTab();

  return (
    <Card className={className}>
      <CardHeader
        title="Memory"
        subtitle={memory ? `${memory.totalEntries} entries` : undefined}
        icon={<Database className="w-4 h-4" />}
        action={
          memory && (
            <span className="text-xs text-dark-500">
              {formatMemorySize(memory.memoryUsage)}
            </span>
          )
        }
      />
      <CardContent>
        {/* Tabs */}
        <div className="flex border-b border-dark-700 mb-4 overflow-x-auto">
          {MEMORY_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => {
                setActiveTab(tab.key);
                queryMemoryMutation.reset();
              }}
              className={`tab flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === tab.key ? 'tab-active' : ''
              }`}
            >
              {tab.icon}
              {tab.label}
              {memory && (
                <Badge
                  variant="neutral"
                  size="sm"
                  className={activeTab === tab.key ? getMemoryLayerBadge(tab.key) : ''}
                >
                  {tab.key === 'short_term' && memory.shortTerm.length}
                  {tab.key === 'working' && memory.working.length}
                  {tab.key === 'long_term' && memory.longTerm.length}
                  {tab.key === 'shared' && memory.shared.length}
                </Badge>
              )}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="flex gap-2 mb-4">
          <Input
            placeholder="Search memory..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            leftIcon={<Search className="w-4 h-4" />}
            className="flex-1"
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={handleSearch}
            isLoading={queryMemoryMutation.isPending}
          >
            Search
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            isLoading={clearMemoryMutation.isPending}
            leftIcon={<Trash2 className="w-4 h-4" />}
          />
        </div>

        {/* Memory Entries */}
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Database className="w-6 h-6 text-dark-500 animate-pulse" />
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-8 text-dark-500">
              <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No {activeTab.replace('_', ' ')} memory entries</p>
            </div>
          ) : (
            entries.map((entry) => (
              <MemoryEntryCard key={entry.id} entry={entry} />
            ))
          )}
        </div>

        {/* Memory Stats */}
        {memory && (
          <div className="mt-4 pt-4 border-t border-dark-700">
            <div className="grid grid-cols-4 gap-2 text-center">
              {MEMORY_TABS.map((tab) => {
                const count =
                  tab.key === 'short_term'
                    ? memory.shortTerm.length
                    : tab.key === 'working'
                    ? memory.working.length
                    : tab.key === 'long_term'
                    ? memory.longTerm.length
                    : memory.shared.length;
                return (
                  <div key={tab.key} className="p-2 bg-dark-900/50 rounded">
                    <div className="text-lg font-semibold text-dark-200">
                      {count}
                    </div>
                    <div className="text-xs text-dark-500">{tab.label}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MemoryPanel;
