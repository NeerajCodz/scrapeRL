import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { MemoryState, MemoryEntry, MemoryLayer } from '@/types';

export function useMemory(episodeId: string | undefined) {
  return useQuery({
    queryKey: ['episode', episodeId, 'memory'],
    queryFn: () => (episodeId ? apiClient.getMemory(episodeId) : null),
    enabled: !!episodeId,
    refetchInterval: 2000,
  });
}

export function useQueryMemory(episodeId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      query,
      layer,
      limit,
    }: {
      query: string;
      layer?: MemoryLayer;
      limit?: number;
    }) =>
      episodeId
        ? apiClient.queryMemory(episodeId, query, layer, limit)
        : Promise.reject(new Error('No episode')),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['episode', episodeId, 'memory'],
      });
    },
  });
}

export function useAddMemory(episodeId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (entry: Omit<MemoryEntry, 'id' | 'timestamp'>) =>
      episodeId
        ? apiClient.addMemory(episodeId, entry)
        : Promise.reject(new Error('No episode')),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['episode', episodeId, 'memory'],
      });
    },
  });
}

export function useClearMemory(episodeId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (layer?: MemoryLayer) =>
      episodeId
        ? apiClient.clearMemory(episodeId, layer)
        : Promise.reject(new Error('No episode')),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['episode', episodeId, 'memory'],
      });
    },
  });
}

export function getMemoryLayerColor(layer: MemoryLayer): string {
  switch (layer) {
    case 'short_term':
      return 'text-yellow-400';
    case 'working':
      return 'text-blue-400';
    case 'long_term':
      return 'text-purple-400';
    case 'shared':
      return 'text-green-400';
    default:
      return 'text-dark-400';
  }
}

export function getMemoryLayerBadge(layer: MemoryLayer): string {
  switch (layer) {
    case 'short_term':
      return 'badge-warning';
    case 'working':
      return 'badge-info';
    case 'long_term':
      return 'badge-neutral';
    case 'shared':
      return 'badge-success';
    default:
      return 'badge-neutral';
  }
}

export function formatMemorySize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export type { MemoryState, MemoryEntry, MemoryLayer };
