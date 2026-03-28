// Core types matching backend models

export type AgentRole = 'navigator' | 'extractor' | 'validator' | 'coordinator';
export type AgentStatus = 'idle' | 'thinking' | 'acting' | 'waiting' | 'error';
export type MemoryLayer = 'short_term' | 'working' | 'long_term' | 'shared';
export type ActionType = 
  | 'navigate' 
  | 'click' 
  | 'extract' 
  | 'scroll' 
  | 'input' 
  | 'wait' 
  | 'screenshot'
  | 'execute_tool'
  | 'delegate'
  | 'terminate';

export interface Position {
  x: number;
  y: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DOMElement {
  tag: string;
  id?: string;
  classes: string[];
  text?: string;
  href?: string;
  src?: string;
  attributes: Record<string, string>;
  boundingBox?: BoundingBox;
  children?: DOMElement[];
}

export interface PageState {
  url: string;
  title: string;
  domain: string;
  loadTime: number;
  contentType: string;
  statusCode: number;
}

export interface Observation {
  step: number;
  timestamp: string;
  page: PageState;
  dom: DOMElement[];
  screenshot?: string;
  extractedData: Record<string, unknown>;
  visibleText: string;
  interactableElements: DOMElement[];
  metadata: Record<string, unknown>;
}

export interface ActionTarget {
  selector?: string;
  xpath?: string;
  text?: string;
  position?: Position;
  element?: DOMElement;
}

export interface Action {
  type: ActionType;
  target?: ActionTarget;
  value?: string;
  parameters?: Record<string, unknown>;
  reasoning?: string;
  confidence: number;
  agentId: string;
  timestamp: string;
}

export interface RewardComponent {
  name: string;
  value: number;
  weight: number;
  description?: string;
}

export interface Reward {
  total: number;
  components: RewardComponent[];
  normalized: number;
  cumulative: number;
  timestamp: string;
}

export interface AgentThought {
  content: string;
  type: 'reasoning' | 'planning' | 'observation' | 'decision';
  timestamp: string;
}

export interface Agent {
  id: string;
  role: AgentRole;
  status: AgentStatus;
  model: string;
  currentTask?: string;
  thoughts: AgentThought[];
  actionsCount: number;
  totalReward: number;
  lastAction?: Action;
  metadata: Record<string, unknown>;
}

export interface MemoryEntry {
  id: string;
  content: string;
  type: string;
  layer: MemoryLayer;
  importance: number;
  timestamp: string;
  expiresAt?: string;
  embedding?: number[];
  metadata: Record<string, unknown>;
}

export interface MemoryState {
  shortTerm: MemoryEntry[];
  working: MemoryEntry[];
  longTerm: MemoryEntry[];
  shared: MemoryEntry[];
  totalEntries: number;
  memoryUsage: number;
}

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  category: string;
  enabled: boolean;
  usageCount: number;
  lastUsed?: string;
}

export interface Task {
  id: string;
  description: string;
  targetUrl: string;
  objectives: string[];
  constraints: string[];
  successCriteria: string[];
  priority: number;
  deadline?: string;
}

export interface EpisodeConfig {
  maxSteps: number;
  timeout: number;
  budget: number;
  allowNavigation: boolean;
  allowInputs: boolean;
  screenshotFrequency: number;
  memoryLimit: number;
}

export interface Episode {
  id: string;
  task: Task;
  config: EpisodeConfig;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'timeout';
  currentStep: number;
  startTime: string;
  endTime?: string;
  totalReward: number;
  observations: Observation[];
  actions: Action[];
  rewards: Reward[];
  agents: Agent[];
  memory: MemoryState;
  success: boolean;
  errorMessage?: string;
}

export interface EpisodeStats {
  totalEpisodes: number;
  successRate: number;
  averageReward: number;
  averageSteps: number;
  totalActions: number;
}

export interface SystemSettings {
  apiKey?: string;
  defaultModel: string;
  availableModels: string[];
  maxConcurrentAgents: number;
  enableWebSocket: boolean;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  screenshotQuality: number;
  memoryPersistence: boolean;
  autoSave: boolean;
  debugMode: boolean;
}

export interface WebSocketMessage {
  type: 'observation' | 'action' | 'reward' | 'agent_update' | 'episode_status' | 'error';
  payload: unknown;
  timestamp: string;
  episodeId?: string;
}

export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
}

export interface StepRequest {
  action: Omit<Action, 'timestamp'>;
  agentId?: string;
}

export interface ResetRequest {
  task: Partial<Task>;
  config?: Partial<EpisodeConfig>;
}
