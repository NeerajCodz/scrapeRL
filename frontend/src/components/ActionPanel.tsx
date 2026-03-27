import React, { useState } from 'react';
import {
  Activity,
  MousePointer,
  Navigation,
  Type,
  Scroll,
  Clock,
  Camera,
  Terminal,
  Users,
  StopCircle,
  ChevronDown,
  ChevronUp,
  Filter,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useEpisodeActions, useCurrentEpisode } from '@/hooks/useEpisode';
import { formatTimestamp, truncateText } from '@/utils/helpers';
import type { Action, ActionType } from '@/types';

interface ActionPanelProps {
  className?: string;
}

const ACTION_ICONS: Record<ActionType, React.ReactNode> = {
  navigate: <Navigation className="w-4 h-4" />,
  click: <MousePointer className="w-4 h-4" />,
  extract: <Terminal className="w-4 h-4" />,
  scroll: <Scroll className="w-4 h-4" />,
  input: <Type className="w-4 h-4" />,
  wait: <Clock className="w-4 h-4" />,
  screenshot: <Camera className="w-4 h-4" />,
  execute_tool: <Terminal className="w-4 h-4" />,
  delegate: <Users className="w-4 h-4" />,
  terminate: <StopCircle className="w-4 h-4" />,
};

const ACTION_COLORS: Record<ActionType, string> = {
  navigate: 'text-blue-400 bg-blue-400/10',
  click: 'text-green-400 bg-green-400/10',
  extract: 'text-purple-400 bg-purple-400/10',
  scroll: 'text-yellow-400 bg-yellow-400/10',
  input: 'text-cyan-400 bg-cyan-400/10',
  wait: 'text-gray-400 bg-gray-400/10',
  screenshot: 'text-pink-400 bg-pink-400/10',
  execute_tool: 'text-orange-400 bg-orange-400/10',
  delegate: 'text-indigo-400 bg-indigo-400/10',
  terminate: 'text-red-400 bg-red-400/10',
};

interface ActionItemProps {
  action: Action;
  index: number;
  isLast: boolean;
}

const ActionItem: React.FC<ActionItemProps> = ({ action, index, isLast }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const iconClass = ACTION_COLORS[action.type] ?? 'text-dark-400 bg-dark-700';

  return (
    <div className="relative">
      {/* Timeline connector */}
      {!isLast && (
        <div className="absolute left-[15px] top-8 bottom-0 w-0.5 bg-dark-700" />
      )}

      <div
        className="flex gap-3 cursor-pointer hover:bg-dark-700/30 rounded-lg p-2 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Icon */}
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${iconClass}`}
        >
          {ACTION_ICONS[action.type]}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="neutral" size="sm" className={iconClass}>
                {action.type}
              </Badge>
              <span className="text-xs text-dark-500">#{index + 1}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-dark-500">
                {formatTimestamp(action.timestamp)}
              </span>
              {isExpanded ? (
                <ChevronUp className="w-3 h-3 text-dark-500" />
              ) : (
                <ChevronDown className="w-3 h-3 text-dark-500" />
              )}
            </div>
          </div>

          {/* Quick info */}
          <div className="mt-1 text-sm text-dark-300">
            {action.target?.selector && (
              <span className="font-mono text-xs text-dark-400">
                {truncateText(action.target.selector, 40)}
              </span>
            )}
            {action.value && (
              <span className="text-dark-400">
                {' → '}
                {truncateText(action.value, 30)}
              </span>
            )}
            {action.reasoning && !action.target?.selector && !action.value && (
              <span className="text-dark-400 italic">
                {truncateText(action.reasoning, 50)}
              </span>
            )}
          </div>

          {/* Confidence bar */}
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1 flex-1 max-w-[100px] bg-dark-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  action.confidence > 0.8
                    ? 'bg-green-500'
                    : action.confidence > 0.5
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`}
                style={{ width: `${action.confidence * 100}%` }}
              />
            </div>
            <span className="text-xs text-dark-500">
              {(action.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="ml-11 mt-2 p-3 bg-dark-900/50 rounded-lg space-y-2">
          {action.reasoning && (
            <div>
              <div className="text-xs text-dark-400 mb-1">Reasoning</div>
              <div className="text-sm text-dark-300">{action.reasoning}</div>
            </div>
          )}

          {action.target && (
            <div>
              <div className="text-xs text-dark-400 mb-1">Target</div>
              <div className="code-block text-xs">
                {JSON.stringify(action.target, null, 2)}
              </div>
            </div>
          )}

          {action.parameters && Object.keys(action.parameters).length > 0 && (
            <div>
              <div className="text-xs text-dark-400 mb-1">Parameters</div>
              <div className="code-block text-xs">
                {JSON.stringify(action.parameters, null, 2)}
              </div>
            </div>
          )}

          <div className="flex items-center gap-4 text-xs text-dark-500">
            <span>Agent: {action.agentId}</span>
            <span>Confidence: {(action.confidence * 100).toFixed(1)}%</span>
          </div>
        </div>
      )}
    </div>
  );
};

export const ActionPanel: React.FC<ActionPanelProps> = ({ className }) => {
  const { data: episode } = useCurrentEpisode();
  const { data: actions, isLoading } = useEpisodeActions(episode?.id);
  const [typeFilter, setTypeFilter] = useState<ActionType | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  const actionTypes = React.useMemo(() => {
    if (!actions) return [];
    return [...new Set(actions.map((a) => a.type))];
  }, [actions]);

  const filteredActions = React.useMemo(() => {
    if (!actions) return [];
    if (!typeFilter) return actions;
    return actions.filter((a) => a.type === typeFilter);
  }, [actions, typeFilter]);

  const actionCounts = React.useMemo(() => {
    if (!actions) return {};
    return actions.reduce(
      (acc, a) => {
        acc[a.type] = (acc[a.type] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  }, [actions]);

  return (
    <Card className={className}>
      <CardHeader
        title="Actions"
        subtitle={`${actions?.length ?? 0} total`}
        icon={<Activity className="w-4 h-4" />}
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="w-4 h-4" />
          </Button>
        }
      />
      <CardContent>
        {/* Filter Bar */}
        {showFilters && (
          <div className="mb-4 p-3 bg-dark-900/50 rounded-lg">
            <div className="text-xs text-dark-400 mb-2">Filter by type</div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setTypeFilter(null)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  !typeFilter
                    ? 'bg-accent-primary text-white'
                    : 'bg-dark-700 text-dark-300 hover:bg-dark-600'
                }`}
              >
                All ({actions?.length ?? 0})
              </button>
              {actionTypes.map((type) => (
                <button
                  key={type}
                  onClick={() =>
                    setTypeFilter(typeFilter === type ? null : type)
                  }
                  className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1 ${
                    typeFilter === type
                      ? ACTION_COLORS[type]
                      : 'bg-dark-700 text-dark-300 hover:bg-dark-600'
                  }`}
                >
                  {ACTION_ICONS[type]}
                  {type} ({actionCounts[type] ?? 0})
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Action Stats */}
        {actions && actions.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {Object.entries(actionCounts)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 5)
              .map(([type, count]) => (
                <Badge
                  key={type}
                  variant="neutral"
                  size="sm"
                  className={ACTION_COLORS[type as ActionType]}
                >
                  {type}: {count}
                </Badge>
              ))}
          </div>
        )}

        {/* Action Timeline */}
        <div className="max-h-[400px] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Activity className="w-6 h-6 text-dark-500 animate-pulse" />
            </div>
          ) : !filteredActions || filteredActions.length === 0 ? (
            <div className="text-center py-8 text-dark-500">
              <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No actions recorded</p>
            </div>
          ) : (
            <div className="space-y-1">
              {filteredActions
                .slice()
                .reverse()
                .map((action, i, arr) => (
                  <ActionItem
                    key={`${action.timestamp}-${i}`}
                    action={action}
                    index={arr.length - 1 - i}
                    isLast={i === arr.length - 1}
                  />
                ))}
            </div>
          )}
        </div>

        {/* Current Action Highlight */}
        {actions && actions.length > 0 && (
          <div className="mt-4 pt-4 border-t border-dark-700">
            <div className="text-xs text-dark-400 mb-2">Latest Action</div>
            <div className="bg-dark-900/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <div
                  className={`p-1.5 rounded ${
                    ACTION_COLORS[actions[actions.length - 1]!.type]
                  }`}
                >
                  {ACTION_ICONS[actions[actions.length - 1]!.type]}
                </div>
                <span className="font-medium text-dark-200">
                  {actions[actions.length - 1]!.type}
                </span>
              </div>
              {actions[actions.length - 1]!.reasoning && (
                <p className="text-sm text-dark-400 mt-1">
                  {actions[actions.length - 1]!.reasoning}
                </p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ActionPanel;
