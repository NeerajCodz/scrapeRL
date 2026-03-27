import React, { useState } from 'react';
import {
  Users,
  Brain,
  MessageSquare,
  Activity,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { useAgents, getAgentRoleIcon, getAgentRoleColor } from '@/hooks/useAgents';
import { useCurrentEpisode } from '@/hooks/useEpisode';
import { formatTimestamp, truncateText } from '@/utils/helpers';
import type { Agent, AgentThought } from '@/types';

interface AgentViewProps {
  className?: string;
}

interface AgentCardProps {
  agent: Agent;
  isExpanded: boolean;
  onToggle: () => void;
}

const ThoughtBubble: React.FC<{ thought: AgentThought }> = ({ thought }) => {
  const typeColors: Record<string, string> = {
    reasoning: 'border-l-blue-400',
    planning: 'border-l-purple-400',
    observation: 'border-l-green-400',
    decision: 'border-l-orange-400',
  };

  return (
    <div
      className={`thought-bubble border-l-2 ${typeColors[thought.type] ?? 'border-l-dark-500'}`}
    >
      <div className="flex items-center gap-2 mb-1">
        <Badge variant="neutral" size="sm">
          {thought.type}
        </Badge>
        <span className="text-xs text-dark-500">
          {formatTimestamp(thought.timestamp)}
        </span>
      </div>
      <p className="text-dark-300">{thought.content}</p>
    </div>
  );
};

const AgentCard: React.FC<AgentCardProps> = ({
  agent,
  isExpanded,
  onToggle,
}) => {
  const roleIcon = getAgentRoleIcon(agent.role);
  const roleColor = getAgentRoleColor(agent.role);

  return (
    <div className="bg-dark-900/50 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full p-3 flex items-center justify-between hover:bg-dark-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="text-2xl">{roleIcon}</div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className={`font-medium capitalize ${roleColor}`}>
                {agent.role}
              </span>
              <StatusBadge status={agent.status} size="sm" />
            </div>
            <div className="text-xs text-dark-500">{agent.model}</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right text-xs text-dark-400">
            <div>{agent.actionsCount} actions</div>
            <div className={agent.totalReward >= 0 ? 'text-green-400' : 'text-red-400'}>
              {agent.totalReward >= 0 ? '+' : ''}{agent.totalReward.toFixed(2)}
            </div>
          </div>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-dark-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-dark-500" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 border-t border-dark-700">
          {/* Current Task */}
          {agent.currentTask && (
            <div className="mt-3 p-2 bg-dark-800 rounded">
              <div className="text-xs text-dark-400 mb-1">Current Task</div>
              <div className="text-sm text-dark-200">{agent.currentTask}</div>
            </div>
          )}

          {/* Last Action */}
          {agent.lastAction && (
            <div className="mt-3 p-2 bg-dark-800 rounded">
              <div className="text-xs text-dark-400 mb-1">Last Action</div>
              <div className="flex items-center gap-2">
                <Badge variant="info" size="sm">
                  {agent.lastAction.type}
                </Badge>
                {agent.lastAction.reasoning && (
                  <span className="text-xs text-dark-400">
                    {truncateText(agent.lastAction.reasoning, 50)}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Thought Stream */}
          {agent.thoughts.length > 0 && (
            <div className="mt-3">
              <div className="flex items-center gap-2 text-xs text-dark-400 mb-2">
                <Brain className="w-3 h-3" />
                <span>Thought Stream</span>
              </div>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {agent.thoughts.slice(-5).map((thought, i) => (
                  <ThoughtBubble key={i} thought={thought} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const AgentView: React.FC<AgentViewProps> = ({ className }) => {
  const { data: episode } = useCurrentEpisode();
  const { data: agents, isLoading } = useAgents(episode?.id);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  const toggleAgent = (agentId: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(agentId)) {
        next.delete(agentId);
      } else {
        next.add(agentId);
      }
      return next;
    });
  };

  const activeAgents = agents?.filter((a) => a.status !== 'idle') ?? [];
  const idleAgents = agents?.filter((a) => a.status === 'idle') ?? [];

  return (
    <Card className={className}>
      <CardHeader
        title="Agents"
        subtitle={`${agents?.length ?? 0} agents`}
        icon={<Users className="w-4 h-4" />}
        action={
          activeAgents.length > 0 && (
            <Badge variant="success" dot pulse>
              {activeAgents.length} active
            </Badge>
          )
        }
      />
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Activity className="w-6 h-6 text-dark-500 animate-pulse" />
          </div>
        ) : !agents || agents.length === 0 ? (
          <div className="text-center py-8 text-dark-500">
            <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No agents active</p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Active Agents */}
            {activeAgents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                isExpanded={expandedAgents.has(agent.id)}
                onToggle={() => toggleAgent(agent.id)}
              />
            ))}

            {/* Idle Agents */}
            {idleAgents.length > 0 && activeAgents.length > 0 && (
              <div className="text-xs text-dark-500 pt-2">Idle Agents</div>
            )}
            {idleAgents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                isExpanded={expandedAgents.has(agent.id)}
                onToggle={() => toggleAgent(agent.id)}
              />
            ))}
          </div>
        )}

        {/* Thought Feed */}
        {agents && agents.some((a) => a.thoughts.length > 0) && (
          <div className="mt-4 pt-4 border-t border-dark-700">
            <div className="flex items-center gap-2 text-sm text-dark-400 mb-3">
              <MessageSquare className="w-4 h-4" />
              <span>Latest Thoughts</span>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {agents
                .flatMap((a) =>
                  a.thoughts.map((t) => ({ ...t, agentId: a.id, role: a.role }))
                )
                .sort(
                  (a, b) =>
                    new Date(b.timestamp).getTime() -
                    new Date(a.timestamp).getTime()
                )
                .slice(0, 5)
                .map((thought, i) => (
                  <div
                    key={i}
                    className="p-2 bg-dark-900/50 rounded text-sm"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs">
                        {getAgentRoleIcon(thought.role)}
                      </span>
                      <span className={`text-xs ${getAgentRoleColor(thought.role)}`}>
                        {thought.role}
                      </span>
                      <span className="text-xs text-dark-500">
                        {formatTimestamp(thought.timestamp)}
                      </span>
                    </div>
                    <p className="text-dark-300 text-xs">
                      {truncateText(thought.content, 100)}
                    </p>
                  </div>
                ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AgentView;
