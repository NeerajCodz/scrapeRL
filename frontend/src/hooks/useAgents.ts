import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { Agent } from '@/types';

export function useAgents(episodeId: string | undefined) {
  return useQuery({
    queryKey: ['episode', episodeId, 'agents'],
    queryFn: () => (episodeId ? apiClient.getAgents(episodeId) : []),
    enabled: !!episodeId,
    refetchInterval: 1000,
  });
}

export function useAgent(episodeId: string | undefined, agentId: string) {
  return useQuery({
    queryKey: ['episode', episodeId, 'agents', agentId],
    queryFn: () =>
      episodeId ? apiClient.getAgent(episodeId, agentId) : null,
    enabled: !!episodeId && !!agentId,
    refetchInterval: 500,
  });
}

export function useUpdateAgent(episodeId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      agentId,
      updates,
    }: {
      agentId: string;
      updates: Partial<Agent>;
    }) =>
      episodeId
        ? apiClient.updateAgent(episodeId, agentId, updates)
        : Promise.reject(new Error('No episode')),
    onSuccess: (_, { agentId }) => {
      queryClient.invalidateQueries({
        queryKey: ['episode', episodeId, 'agents', agentId],
      });
      queryClient.invalidateQueries({
        queryKey: ['episode', episodeId, 'agents'],
      });
    },
  });
}

export function getAgentStatusVariant(
  status: Agent['status']
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  switch (status) {
    case 'acting':
      return 'success';
    case 'thinking':
      return 'info';
    case 'waiting':
      return 'warning';
    case 'error':
      return 'error';
    case 'idle':
    default:
      return 'neutral';
  }
}

export function getAgentRoleColor(role: Agent['role']): string {
  switch (role) {
    case 'navigator':
      return 'text-blue-400';
    case 'extractor':
      return 'text-purple-400';
    case 'validator':
      return 'text-green-400';
    case 'coordinator':
      return 'text-orange-400';
    default:
      return 'text-dark-400';
  }
}

export function getAgentRoleIcon(role: Agent['role']): string {
  switch (role) {
    case 'navigator':
      return '🧭';
    case 'extractor':
      return '📊';
    case 'validator':
      return '✅';
    case 'coordinator':
      return '🎯';
    default:
      return '🤖';
  }
}

export type { Agent };
