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

// Scraping types
export interface ScrapeRequest {
  assets: string[];
  instructions: string;
  output_instructions: string;
  output_format: 'json' | 'csv' | 'markdown' | 'text';
  complexity: 'low' | 'medium' | 'high';
  model: string;
  provider: string;
  enable_memory: boolean;
  enable_plugins: string[];
  selected_agents: string[];
  max_steps: number;
  python_code?: string;
}

export interface ScrapeStep {
  step_number: number;
  action: string;
  url: string | null;
  status: string;
  message: string;
  reward: number;
  extracted_data: Record<string, unknown> | null;
  duration_ms: number | null;
  timestamp: string;
}

export interface ScrapeResponse {
  session_id: string;
  status: string;
  total_steps: number;
  total_reward: number;
  extracted_data: Record<string, unknown>;
  output: string;
  output_format: string;
  duration_seconds: number;
  urls_processed: number;
  errors: string[];
  selected_agents?: string[];
  sandbox_artifacts?: string[];
}

export interface StreamEvent {
  type: 'init' | 'url_start' | 'step' | 'url_complete' | 'complete' | 'error';
  session_id?: string;
  url?: string;
  index?: number;
  total?: number;
  data?: ScrapeStep | ScrapeResponse | { url: string; error: string };
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
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) {
      throw new APIError('Health check failed', response.status);
    }
    return response.json();
  },

  // Scraping with streaming
  streamScrape(
    scrapeRequest: ScrapeRequest,
    onInit?: (sessionId: string) => void,
    onUrlStart?: (url: string, index: number, total: number) => void,
    onStep?: (step: ScrapeStep) => void,
    onUrlComplete?: (url: string, index: number) => void,
    onComplete?: (response: ScrapeResponse) => void,
    onError?: (error: string, url?: string) => void
  ): { abort: () => void } {
    const abortController = new AbortController();

    fetch(`${API_BASE}/scrape/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(scrapeRequest),
      signal: abortController.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          onError?.(errorData.detail || 'Stream failed');
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          onError?.('No response body');
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event: StreamEvent = JSON.parse(line.slice(6));
                
                switch (event.type) {
                  case 'init':
                    onInit?.(event.session_id!);
                    break;
                  case 'url_start':
                    onUrlStart?.(event.url!, event.index!, event.total!);
                    break;
                  case 'step':
                    onStep?.(event.data as ScrapeStep);
                    break;
                  case 'url_complete':
                    onUrlComplete?.(event.url!, event.index!);
                    break;
                  case 'complete':
                    onComplete?.(event.data as ScrapeResponse);
                    break;
                  case 'error':
                    const errData = event.data as { url: string; error: string };
                    onError?.(errData.error, errData.url);
                    break;
                }
              } catch {
                // Ignore parse errors
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError?.(err.message || 'Stream failed');
        }
      });

    return { abort: () => abortController.abort() };
  },

  // Get scrape session status
  async getScrapeStatus(sessionId: string): Promise<{
    session_id: string;
    status: string;
    current_url_index: number;
    total_urls: number;
    total_reward: number;
    extracted_count: number;
    errors: string[];
    duration: number;
  }> {
    const response = await fetch(`${API_BASE}/scrape/${sessionId}/status`);
    if (!response.ok) {
      throw new APIError('Failed to get scrape status', response.status);
    }
    return response.json();
  },

  // Get scrape result
  async getScrapeResult(sessionId: string): Promise<ScrapeResponse> {
    const response = await fetch(`${API_BASE}/scrape/${sessionId}/result`);
    if (!response.ok) {
      throw new APIError('Failed to get scrape result', response.status);
    }
    return response.json();
  },
};

export { APIError };
export default apiClient;
