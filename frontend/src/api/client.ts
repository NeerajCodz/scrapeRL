import type {
  Episode,
  Observation,
  Action,
  Reward,
  Agent,
  MemoryState,
  MCPTool,
  SystemSettings,
  APIResponse,
  StepRequest,
  ResetRequest,
  EpisodeStats,
} from '@/types';

const API_BASE = '/api';

class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const data = await response.json() as APIResponse<T>;

  if (!response.ok) {
    throw new APIError(
      data.error ?? 'An error occurred',
      response.status,
      data
    );
  }

  if (!data.success) {
    throw new APIError(data.error ?? 'Request failed', response.status, data);
  }

  return data.data as T;
}

export const apiClient = {
  // Episode Management
  async resetEpisode(params: ResetRequest): Promise<Episode> {
    return request<Episode>('/episode/reset', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async getEpisode(episodeId: string): Promise<Episode> {
    return request<Episode>(`/episode/${episodeId}`);
  },

  async getCurrentEpisode(): Promise<Episode | null> {
    try {
      return await request<Episode>('/episode/current');
    } catch (error) {
      if (error instanceof APIError && error.status === 404) {
        return null;
      }
      throw error;
    }
  },

  async stepEpisode(episodeId: string, step: StepRequest): Promise<{
    observation: Observation;
    reward: Reward;
    done: boolean;
    info: Record<string, unknown>;
  }> {
    return request(`/episode/${episodeId}/step`, {
      method: 'POST',
      body: JSON.stringify(step),
    });
  },

  async terminateEpisode(episodeId: string): Promise<Episode> {
    return request<Episode>(`/episode/${episodeId}/terminate`, {
      method: 'POST',
    });
  },

  // State Queries
  async getState(episodeId: string): Promise<{
    observation: Observation;
    agents: Agent[];
    memory: MemoryState;
  }> {
    return request(`/episode/${episodeId}/state`);
  },

  async getObservation(episodeId: string, step?: number): Promise<Observation> {
    const query = step !== undefined ? `?step=${step}` : '';
    return request<Observation>(`/episode/${episodeId}/observation${query}`);
  },

  async getActions(episodeId: string): Promise<Action[]> {
    return request<Action[]>(`/episode/${episodeId}/actions`);
  },

  async getRewards(episodeId: string): Promise<Reward[]> {
    return request<Reward[]>(`/episode/${episodeId}/rewards`);
  },

  // Agent Management
  async getAgents(episodeId: string): Promise<Agent[]> {
    return request<Agent[]>(`/episode/${episodeId}/agents`);
  },

  async getAgent(episodeId: string, agentId: string): Promise<Agent> {
    return request<Agent>(`/episode/${episodeId}/agents/${agentId}`);
  },

  async updateAgent(
    episodeId: string,
    agentId: string,
    updates: Partial<Agent>
  ): Promise<Agent> {
    return request<Agent>(`/episode/${episodeId}/agents/${agentId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  },

  // Memory Operations
  async getMemory(episodeId: string): Promise<MemoryState> {
    return request<MemoryState>(`/episode/${episodeId}/memory`);
  },

  async queryMemory(
    episodeId: string,
    query: string,
    layer?: string,
    limit?: number
  ): Promise<import('@/types').MemoryEntry[]> {
    const params = new URLSearchParams({ query });
    if (layer) params.set('layer', layer);
    if (limit) params.set('limit', limit.toString());
    return request(`/episode/${episodeId}/memory/query?${params}`);
  },

  async addMemory(
    episodeId: string,
    entry: Omit<import('@/types').MemoryEntry, 'id' | 'timestamp'>
  ): Promise<import('@/types').MemoryEntry> {
    return request(`/episode/${episodeId}/memory`, {
      method: 'POST',
      body: JSON.stringify(entry),
    });
  },

  async clearMemory(episodeId: string, layer?: string): Promise<void> {
    const query = layer ? `?layer=${layer}` : '';
    return request(`/episode/${episodeId}/memory${query}`, {
      method: 'DELETE',
    });
  },

  // Tools
  async getTools(): Promise<MCPTool[]> {
    return request<MCPTool[]>('/tools');
  },

  async getTool(name: string): Promise<MCPTool> {
    return request<MCPTool>(`/tools/${name}`);
  },

  async executeTool(
    name: string,
    parameters: Record<string, unknown>
  ): Promise<unknown> {
    return request(`/tools/${name}/execute`, {
      method: 'POST',
      body: JSON.stringify(parameters),
    });
  },

  async toggleTool(name: string, enabled: boolean): Promise<MCPTool> {
    return request<MCPTool>(`/tools/${name}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    });
  },

  // Settings
  async getSettings(): Promise<SystemSettings> {
    return request<SystemSettings>('/settings');
  },

  async updateSettings(settings: Partial<SystemSettings>): Promise<SystemSettings> {
    return request<SystemSettings>('/settings', {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  },

  // Stats
  async getStats(): Promise<EpisodeStats> {
    return request<EpisodeStats>('/stats');
  },

  // Health Check
  async healthCheck(): Promise<{ status: string; version: string }> {
    return request('/health');
  },
};

export { APIError };
export default apiClient;
