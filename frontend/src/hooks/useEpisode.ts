import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { Episode, ResetRequest, StepRequest, Action } from '@/types';

export function useCurrentEpisode() {
  return useQuery({
    queryKey: ['episode', 'current'],
    queryFn: () => apiClient.getCurrentEpisode(),
    refetchInterval: 2000,
  });
}

export function useEpisode(episodeId: string | undefined) {
  return useQuery({
    queryKey: ['episode', episodeId],
    queryFn: () => (episodeId ? apiClient.getEpisode(episodeId) : null),
    enabled: !!episodeId,
    refetchInterval: 1000,
  });
}

export function useResetEpisode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: ResetRequest) => apiClient.resetEpisode(params),
    onSuccess: (episode) => {
      queryClient.setQueryData(['episode', 'current'], episode);
      queryClient.setQueryData(['episode', episode.id], episode);
      queryClient.invalidateQueries({ queryKey: ['episode'] });
    },
  });
}

export function useStepEpisode(episodeId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (step: StepRequest) =>
      episodeId
        ? apiClient.stepEpisode(episodeId, step)
        : Promise.reject(new Error('No episode')),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['episode', episodeId] });
      queryClient.invalidateQueries({ queryKey: ['episode', 'current'] });
    },
  });
}

export function useTerminateEpisode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (episodeId: string) => apiClient.terminateEpisode(episodeId),
    onSuccess: (_, episodeId) => {
      queryClient.invalidateQueries({ queryKey: ['episode', episodeId] });
      queryClient.invalidateQueries({ queryKey: ['episode', 'current'] });
    },
  });
}

export function useEpisodeActions(episodeId: string | undefined) {
  return useQuery({
    queryKey: ['episode', episodeId, 'actions'],
    queryFn: () => (episodeId ? apiClient.getActions(episodeId) : []),
    enabled: !!episodeId,
    refetchInterval: 1000,
  });
}

export function useEpisodeRewards(episodeId: string | undefined) {
  return useQuery({
    queryKey: ['episode', episodeId, 'rewards'],
    queryFn: () => (episodeId ? apiClient.getRewards(episodeId) : []),
    enabled: !!episodeId,
    refetchInterval: 1000,
  });
}

export function useEpisodeStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: () => apiClient.getStats(),
    refetchInterval: 5000,
  });
}

export function useEpisodeState(episodeId: string | undefined) {
  return useQuery({
    queryKey: ['episode', episodeId, 'state'],
    queryFn: () => (episodeId ? apiClient.getState(episodeId) : null),
    enabled: !!episodeId,
    refetchInterval: 500,
  });
}

// Helper to create a quick action
export function createAction(
  type: Action['type'],
  agentId: string,
  options: Partial<Omit<Action, 'type' | 'agentId' | 'timestamp'>> = {}
): StepRequest {
  return {
    action: {
      type,
      agentId,
      confidence: 1.0,
      ...options,
    },
    agentId,
  };
}

export type { Episode, ResetRequest, StepRequest };
