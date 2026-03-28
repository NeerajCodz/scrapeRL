import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  Zap,
  Target,
  Clock,
  TrendingUp,
  Database,
  Cpu,
  Globe,
  Play,
  Pause,
  ChevronDown,
  ChevronRight,
  MoreHorizontal,
  Terminal,
  Settings,
  Wrench,
  Plug,
  Eye,
  Bot,
  X,
  Check,
  Layers,
  FileText,
  List,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { classNames } from '@/utils/helpers';
import { apiClient } from '@/api/client';

// Types
interface TaskInput {
  url: string;
  instruction: string;
  taskType: 'low' | 'medium' | 'high';
  selectedModel: string;
  selectedAgents: string[];
  enabledPlugins: string[];
}

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  source?: string;
}

interface EpisodeStats {
  total: number;
  min: number;
  max: number;
  avg: number;
}

interface AgentOption {
  id: string;
  name: string;
  description: string;
  active?: boolean;
}

interface ModelOption {
  provider: string;
  model: string;
  name: string;
}

// Popup Components
interface PopupProps {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

const Popup: React.FC<PopupProps> = ({ title, isOpen, onClose, children }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <h3 className="font-semibold text-white">{title}</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 overflow-y-auto max-h-[60vh]">{children}</div>
      </div>
    </div>
  );
};

// Stats Popup
const StatsPopup: React.FC<{ isOpen: boolean; onClose: () => void; stats: EpisodeStats; title: string }> = ({
  isOpen,
  onClose,
  stats,
  title,
}) => (
  <Popup title={title} isOpen={isOpen} onClose={onClose}>
    <div className="grid grid-cols-2 gap-4">
      <div className="p-4 bg-gray-900/50 rounded-lg text-center">
        <p className="text-2xl font-bold text-emerald-400">{stats.total}</p>
        <p className="text-xs text-gray-400">Total</p>
      </div>
      <div className="p-4 bg-gray-900/50 rounded-lg text-center">
        <p className="text-2xl font-bold text-cyan-400">{stats.avg.toFixed(2)}</p>
        <p className="text-xs text-gray-400">Average</p>
      </div>
      <div className="p-4 bg-gray-900/50 rounded-lg text-center">
        <p className="text-2xl font-bold text-amber-400">{stats.min.toFixed(2)}</p>
        <p className="text-xs text-gray-400">Minimum</p>
      </div>
      <div className="p-4 bg-gray-900/50 rounded-lg text-center">
        <p className="text-2xl font-bold text-purple-400">{stats.max.toFixed(2)}</p>
        <p className="text-xs text-gray-400">Maximum</p>
      </div>
    </div>
  </Popup>
);

// Accordion Component
interface AccordionProps {
  title: string;
  icon: React.ElementType;
  badge?: string | number;
  color: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

const Accordion: React.FC<AccordionProps> = ({ title, icon: Icon, badge, color, children, defaultOpen = false }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  
  return (
    <div className="border border-gray-700/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2.5 bg-gray-800/50 hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${color}`} />
          <span className="text-sm font-medium text-white">{title}</span>
          {badge !== undefined && (
            <Badge variant="neutral" size="sm">{badge}</Badge>
          )}
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
      </button>
      {isOpen && <div className="p-3 bg-gray-900/30 border-t border-gray-700/50">{children}</div>}
    </div>
  );
};

// Main Dashboard Component
export const Dashboard: React.FC = () => {
  // State
  const [taskInput, setTaskInput] = useState<TaskInput>({
    url: '',
    instruction: '',
    taskType: 'medium',
    selectedModel: 'groq/gpt-oss-120b',
    selectedAgents: ['coordinator', 'scraper'],
    enabledPlugins: ['browser-use', 'firecrawl'],
  });
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: '1', timestamp: new Date().toISOString(), level: 'info', message: 'System initialized', source: 'system' },
    { id: '2', timestamp: new Date().toISOString(), level: 'info', message: 'Ready to start episode', source: 'coordinator' },
  ]);
  const [isRunning, setIsRunning] = useState(false);
  const [showModelPopup, setShowModelPopup] = useState(false);
  const [showAgentPopup, setShowAgentPopup] = useState(false);
  const [showPluginPopup, setShowPluginPopup] = useState(false);
  const [showTaskTypePopup, setShowTaskTypePopup] = useState(false);
  const [showStatsPopup, setShowStatsPopup] = useState<'episodes' | 'steps' | 'reward' | null>(null);

  // API Queries
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.healthCheck(),
    refetchInterval: 5000,
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const res = await fetch('/api/agents/');
      return res.json();
    },
  });

  useQuery({
    queryKey: ['plugins'],
    queryFn: async () => {
      const res = await fetch('/api/plugins/');
      return res.json();
    },
  });

  const { data: memoryData } = useQuery({
    queryKey: ['memory-stats'],
    queryFn: async () => {
      const res = await fetch('/api/memory/stats/overview');
      return res.json();
    },
    refetchInterval: 3000,
  });

  const { data: settingsData } = useQuery({
    queryKey: ['client-settings'],
    queryFn: async () => {
      const res = await fetch('/api/settings/');
      return res.json();
    },
  });

  // Episode Stats (mock data for now)
  const episodeStats: EpisodeStats = { total: 12, min: 3, max: 47, avg: 18.5 };
  const stepStats: EpisodeStats = { total: 156, min: 5, max: 89, avg: 23.4 };
  const rewardStats: EpisodeStats = { total: 847.5, min: -12.3, max: 98.7, avg: 70.6 };

  // Available options
  const availableModels: ModelOption[] = settingsData?.available_models ?? [
    { provider: 'groq', model: 'gpt-oss-120b', name: 'GPT-OSS 120B (Groq)' },
    { provider: 'google', model: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
    { provider: 'openai', model: 'gpt-4-turbo', name: 'GPT-4 Turbo' },
    { provider: 'anthropic', model: 'claude-3-opus', name: 'Claude 3 Opus' },
  ];

  const availableAgents: AgentOption[] = agentsData?.agents ?? [
    { id: 'coordinator', name: 'Coordinator', description: 'Orchestrates all agents', active: true },
    { id: 'scraper', name: 'Scraper', description: 'Extracts data from pages', active: true },
    { id: 'navigator', name: 'Navigator', description: 'Handles page navigation', active: false },
    { id: 'analyzer', name: 'Analyzer', description: 'Analyzes extracted data', active: false },
    { id: 'validator', name: 'Validator', description: 'Validates data quality', active: false },
  ];

  const pluginCategories = {
    mcps: [
      { id: 'browser-use', name: 'Browser Use', enabled: true, status: 'active' },
      { id: 'puppeteer-mcp', name: 'Puppeteer MCP', enabled: false, status: 'idle' },
      { id: 'playwright-mcp', name: 'Playwright MCP', enabled: false, status: 'idle' },
    ],
    skills: [
      { id: 'web-scraping', name: 'Web Scraping', enabled: true, status: 'active' },
      { id: 'data-extraction', name: 'Data Extraction', enabled: true, status: 'active' },
      { id: 'form-filling', name: 'Form Filling', enabled: false, status: 'idle' },
    ],
    apis: [
      { id: 'firecrawl', name: 'Firecrawl', enabled: true, status: 'active' },
      { id: 'jina-reader', name: 'Jina Reader', enabled: false, status: 'idle' },
      { id: 'serper', name: 'Serper API', enabled: false, status: 'idle' },
    ],
    vision: [
      { id: 'gpt4-vision', name: 'GPT-4 Vision', enabled: false, status: 'idle' },
      { id: 'gemini-vision', name: 'Gemini Vision', enabled: false, status: 'idle' },
      { id: 'claude-vision', name: 'Claude Vision', enabled: false, status: 'idle' },
    ],
  };

  const taskTypes = [
    { id: 'low', name: 'Low Complexity', description: 'Simple single-page scraping', color: 'emerald' },
    { id: 'medium', name: 'Medium Complexity', description: 'Multi-page with navigation', color: 'amber' },
    { id: 'high', name: 'High Complexity', description: 'Complex interactive tasks', color: 'red' },
  ];

  const handleStart = () => {
    setIsRunning(true);
    const newLog: LogEntry = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `Starting episode with URL: ${taskInput.url}`,
      source: 'coordinator',
    };
    setLogs((prev) => [...prev, newLog]);
  };

  const handleStop = () => {
    setIsRunning(false);
    const newLog: LogEntry = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      level: 'warn',
      message: 'Episode stopped by user',
      source: 'system',
    };
    setLogs((prev) => [...prev, newLog]);
  };

  const formatTime = (isoString: string) => {
    return new Date(isoString).toLocaleTimeString('en-US', { hour12: false });
  };

  const getLogLevelColor = (level: LogEntry['level']) => {
    const colors = {
      info: 'text-cyan-400',
      warn: 'text-amber-400',
      error: 'text-red-400',
      debug: 'text-gray-400',
    };
    return colors[level];
  };

  return (
    <div className="h-[calc(100vh-80px)] flex flex-col">
      {/* Input Section */}
      <div className="flex-shrink-0 p-4 bg-gray-800/50 border-b border-gray-700/50">
        <div className="flex flex-wrap items-end gap-4">
          {/* URL Input */}
          <div className="flex-1 min-w-[300px]">
            <label className="text-xs text-gray-400 mb-1 block">Target URL</label>
            <input
              type="url"
              placeholder="https://example.com/page-to-scrape"
              value={taskInput.url}
              onChange={(e) => setTaskInput((p) => ({ ...p, url: e.target.value }))}
              className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50"
            />
          </div>

          {/* Instruction */}
          <div className="flex-1 min-w-[300px]">
            <label className="text-xs text-gray-400 mb-1 block">Instruction</label>
            <input
              type="text"
              placeholder="Extract all product prices and names..."
              value={taskInput.instruction}
              onChange={(e) => setTaskInput((p) => ({ ...p, instruction: e.target.value }))}
              className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50"
            />
          </div>

          {/* Selection Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowModelPopup(true)}
              className="px-3 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              <Cpu className="w-4 h-4" />
              Model
            </button>
            <button
              onClick={() => setShowAgentPopup(true)}
              className="px-3 py-2 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              <Bot className="w-4 h-4" />
              Agents
            </button>
            <button
              onClick={() => setShowPluginPopup(true)}
              className="px-3 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              <Plug className="w-4 h-4" />
              Plugins
            </button>
            <button
              onClick={() => setShowTaskTypePopup(true)}
              className={classNames(
                'px-3 py-2 border rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
                taskInput.taskType === 'low' && 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
                taskInput.taskType === 'medium' && 'bg-amber-500/10 border-amber-500/30 text-amber-400',
                taskInput.taskType === 'high' && 'bg-red-500/10 border-red-500/30 text-red-400'
              )}
            >
              <Target className="w-4 h-4" />
              {taskInput.taskType.charAt(0).toUpperCase() + taskInput.taskType.slice(1)}
            </button>
          </div>

          {/* Start/Stop Button */}
          {isRunning ? (
            <button
              onClick={handleStop}
              className="px-5 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2 shadow-lg shadow-red-500/20"
            >
              <Pause className="w-4 h-4" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={!taskInput.url}
              className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center gap-2 shadow-lg shadow-emerald-500/20"
            >
              <Play className="w-4 h-4" />
              Start
            </button>
          )}
        </div>
      </div>

      {/* Main Content - 3 Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Accordions */}
        <div className="w-64 flex-shrink-0 bg-gray-800/30 border-r border-gray-700/50 overflow-y-auto p-3 space-y-2">
          {/* Agents Accordion */}
          <Accordion title="Agents" icon={Bot} badge={taskInput.selectedAgents.length} color="text-purple-400" defaultOpen>
            <div className="space-y-2">
              {availableAgents.map((agent) => {
                const isActive = taskInput.selectedAgents.includes(agent.id);
                return (
                  <div
                    key={agent.id}
                    className={classNames(
                      'flex items-center justify-between p-2 rounded-lg transition-colors',
                      isActive ? 'bg-purple-500/10 border border-purple-500/30' : 'bg-gray-800/50'
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <div className={classNames('w-2 h-2 rounded-full', isActive ? 'bg-emerald-400' : 'bg-gray-500')} />
                      <span className="text-xs text-white">{agent.name}</span>
                    </div>
                    {isActive && <Clock className="w-3 h-3 text-gray-400" />}
                  </div>
                );
              })}
            </div>
          </Accordion>

          {/* MCPs Accordion */}
          <Accordion title="MCPs" icon={Wrench} badge={pluginCategories.mcps.filter(p => p.enabled).length} color="text-amber-400">
            <div className="space-y-2">
              {pluginCategories.mcps.map((plugin) => (
                <div
                  key={plugin.id}
                  className={classNames(
                    'flex items-center justify-between p-2 rounded-lg',
                    plugin.enabled ? 'bg-amber-500/10 border border-amber-500/30' : 'bg-gray-800/50'
                  )}
                >
                  <span className="text-xs text-white">{plugin.name}</span>
                  <Badge variant={plugin.status === 'active' ? 'success' : 'neutral'} size="sm">
                    {plugin.status}
                  </Badge>
                </div>
              ))}
            </div>
          </Accordion>

          {/* Skills Accordion */}
          <Accordion title="Skills" icon={Zap} badge={pluginCategories.skills.filter(p => p.enabled).length} color="text-cyan-400">
            <div className="space-y-2">
              {pluginCategories.skills.map((plugin) => (
                <div
                  key={plugin.id}
                  className={classNames(
                    'flex items-center justify-between p-2 rounded-lg',
                    plugin.enabled ? 'bg-cyan-500/10 border border-cyan-500/30' : 'bg-gray-800/50'
                  )}
                >
                  <span className="text-xs text-white">{plugin.name}</span>
                  <Badge variant={plugin.status === 'active' ? 'success' : 'neutral'} size="sm">
                    {plugin.status}
                  </Badge>
                </div>
              ))}
            </div>
          </Accordion>

          {/* APIs Accordion */}
          <Accordion title="APIs" icon={Plug} badge={pluginCategories.apis.filter(p => p.enabled).length} color="text-emerald-400">
            <div className="space-y-2">
              {pluginCategories.apis.map((plugin) => (
                <div
                  key={plugin.id}
                  className={classNames(
                    'flex items-center justify-between p-2 rounded-lg',
                    plugin.enabled ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-gray-800/50'
                  )}
                >
                  <span className="text-xs text-white">{plugin.name}</span>
                  <Badge variant={plugin.status === 'active' ? 'success' : 'neutral'} size="sm">
                    {plugin.status}
                  </Badge>
                </div>
              ))}
            </div>
          </Accordion>

          {/* Vision Accordion */}
          <Accordion title="Vision" icon={Eye} badge={pluginCategories.vision.filter(p => p.enabled).length} color="text-pink-400">
            <div className="space-y-2">
              {pluginCategories.vision.map((plugin) => (
                <div
                  key={plugin.id}
                  className={classNames(
                    'flex items-center justify-between p-2 rounded-lg',
                    plugin.enabled ? 'bg-pink-500/10 border border-pink-500/30' : 'bg-gray-800/50'
                  )}
                >
                  <span className="text-xs text-white">{plugin.name}</span>
                  <Badge variant={plugin.status === 'active' ? 'success' : 'neutral'} size="sm">
                    {plugin.status}
                  </Badge>
                </div>
              ))}
            </div>
          </Accordion>

          {/* Tools Accordion */}
          <Accordion title="Tools" icon={Wrench} color="text-blue-400">
            <div className="space-y-2 text-xs text-gray-400">
              <div className="flex items-center justify-between p-2 bg-gray-800/50 rounded-lg">
                <span>HTTP Client</span>
                <Badge variant="success" size="sm">ready</Badge>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-800/50 rounded-lg">
                <span>HTML Parser</span>
                <Badge variant="success" size="sm">ready</Badge>
              </div>
              <div className="flex items-center justify-between p-2 bg-gray-800/50 rounded-lg">
                <span>JSON Extractor</span>
                <Badge variant="success" size="sm">ready</Badge>
              </div>
            </div>
          </Accordion>
        </div>

        {/* Center Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Stats Header */}
          <div className="flex-shrink-0 p-3 bg-gray-800/30 border-b border-gray-700/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                {/* Episodes */}
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-emerald-500/20 rounded">
                    <Layers className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white">{episodeStats.total}</p>
                    <p className="text-[10px] text-gray-500">Episodes</p>
                  </div>
                  <button
                    onClick={() => setShowStatsPopup('episodes')}
                    className="p-1 text-gray-500 hover:text-gray-300"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                </div>

                {/* Steps */}
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-cyan-500/20 rounded">
                    <Target className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white">{stepStats.total}</p>
                    <p className="text-[10px] text-gray-500">Steps</p>
                  </div>
                  <button
                    onClick={() => setShowStatsPopup('steps')}
                    className="p-1 text-gray-500 hover:text-gray-300"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                </div>

                {/* Reward */}
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-purple-500/20 rounded">
                    <TrendingUp className="w-4 h-4 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white">{rewardStats.avg.toFixed(1)}</p>
                    <p className="text-[10px] text-gray-500">Avg Reward</p>
                  </div>
                  <button
                    onClick={() => setShowStatsPopup('reward')}
                    className="p-1 text-gray-500 hover:text-gray-300"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Time & Status */}
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-sm font-mono text-white">{new Date().toLocaleTimeString()}</p>
                  <p className="text-[10px] text-gray-500">Current Time</p>
                </div>
                <div className={classNames('px-3 py-1.5 rounded-lg flex items-center gap-2', isRunning ? 'bg-emerald-500/20' : 'bg-gray-700/50')}>
                  <div className={classNames('w-2 h-2 rounded-full', isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500')} />
                  <span className={classNames('text-sm font-medium', isRunning ? 'text-emerald-400' : 'text-gray-400')}>
                    {isRunning ? 'Running' : 'Idle'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Main Visualization Area */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="h-full bg-gray-900/50 border border-gray-700/50 rounded-xl p-4">
              {isRunning ? (
                <div className="h-full flex flex-col">
                  {/* Current Action */}
                  <div className="flex-shrink-0 mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                      <span className="text-sm font-medium text-white">Current Action</span>
                    </div>
                    <div className="p-3 bg-gray-800/50 rounded-lg">
                      <p className="text-sm text-gray-300">Navigating to: {taskInput.url}</p>
                      <p className="text-xs text-gray-500 mt-1">Agent: Scraper | Step: 1/10</p>
                    </div>
                  </div>

                  {/* Observation Preview */}
                  <div className="flex-1 overflow-auto">
                    <div className="flex items-center gap-2 mb-2">
                      <Globe className="w-4 h-4 text-cyan-400" />
                      <span className="text-sm font-medium text-white">Page Observation</span>
                    </div>
                    <div className="p-3 bg-gray-800/50 rounded-lg min-h-[200px]">
                      <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap">
{`{
  "url": "${taskInput.url || 'N/A'}",
  "title": "Loading...",
  "elements": [],
  "links": [],
  "text_content": "..."
}`}
                      </pre>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center">
                  <div className="w-16 h-16 bg-gray-800/50 rounded-full flex items-center justify-center mb-4">
                    <Play className="w-8 h-8 text-gray-500" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-300 mb-2">Ready to Start</h3>
                  <p className="text-sm text-gray-500 max-w-md">
                    Enter a URL and instruction above, configure your agents and plugins, then click Start to begin scraping.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Logs Terminal */}
          <div className="flex-shrink-0 h-36 bg-gray-900 border-t border-gray-700/50">
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-gray-500" />
                <span className="text-xs font-medium text-gray-400">Logs</span>
              </div>
              <button
                onClick={() => setLogs([])}
                className="text-xs text-gray-500 hover:text-gray-300"
              >
                Clear
              </button>
            </div>
            <div className="h-[calc(100%-28px)] overflow-y-auto p-2 font-mono text-xs">
              {logs.map((log) => (
                <div key={log.id} className="flex items-start gap-2 py-0.5">
                  <span className="text-gray-600">[{formatTime(log.timestamp)}]</span>
                  <span className={getLogLevelColor(log.level)}>[{log.level.toUpperCase()}]</span>
                  {log.source && <span className="text-purple-400">[{log.source}]</span>}
                  <span className="text-gray-300">{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Sidebar - Memory & Data */}
        <div className="w-72 flex-shrink-0 bg-gray-800/30 border-l border-gray-700/50 overflow-y-auto p-3 space-y-3">
          {/* Memory Stats */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-3">
              <Database className="w-4 h-4 text-pink-400" />
              <span className="text-sm font-medium text-white">Memory</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 bg-gray-800/50 rounded text-center">
                <p className="text-lg font-bold text-emerald-400">{memoryData?.working?.count || 0}</p>
                <p className="text-[10px] text-gray-500">Working</p>
              </div>
              <div className="p-2 bg-gray-800/50 rounded text-center">
                <p className="text-lg font-bold text-cyan-400">{memoryData?.episodic?.count || 0}</p>
                <p className="text-[10px] text-gray-500">Episodic</p>
              </div>
              <div className="p-2 bg-gray-800/50 rounded text-center">
                <p className="text-lg font-bold text-purple-400">{memoryData?.semantic?.count || 0}</p>
                <p className="text-[10px] text-gray-500">Semantic</p>
              </div>
              <div className="p-2 bg-gray-800/50 rounded text-center">
                <p className="text-lg font-bold text-amber-400">{memoryData?.procedural?.count || 0}</p>
                <p className="text-[10px] text-gray-500">Procedural</p>
              </div>
            </div>
          </div>

          {/* Extracted Data */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-medium text-white">Extracted Data</span>
              </div>
              <Badge variant="neutral" size="sm">0 items</Badge>
            </div>
            <div className="text-center py-6 text-gray-500 text-xs">
              No data extracted yet.<br />Start an episode to begin.
            </div>
          </div>

          {/* Recent Actions */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-3">
              <List className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium text-white">Recent Actions</span>
            </div>
            <div className="space-y-2">
              {isRunning ? (
                <>
                  <div className="flex items-center gap-2 p-2 bg-emerald-500/10 rounded">
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span className="text-xs text-gray-300">Navigate to URL</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-gray-800/50 rounded">
                    <Activity className="w-3 h-3 text-cyan-400 animate-pulse" />
                    <span className="text-xs text-gray-300">Loading page...</span>
                  </div>
                </>
              ) : (
                <div className="text-center py-4 text-gray-500 text-xs">
                  No recent actions
                </div>
              )}
            </div>
          </div>

          {/* System Info */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-3">
              <Settings className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-medium text-white">System</span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Status</span>
                <Badge variant={health?.status === 'ok' ? 'success' : 'error'} size="sm">
                  {health?.status === 'ok' ? 'Online' : 'Offline'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Model</span>
                <span className="text-gray-300">{taskInput.selectedModel.split('/')[1]}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Version</span>
                <span className="text-gray-300">{health?.version || 'v0.1.0'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Popups */}
      {/* Model Selection Popup */}
      <Popup title="Select Model" isOpen={showModelPopup} onClose={() => setShowModelPopup(false)}>
        <div className="space-y-2">
          {availableModels.map((model: { provider: string; model: string; name: string }) => (
            <button
              key={`${model.provider}/${model.model}`}
              onClick={() => {
                setTaskInput((p) => ({ ...p, selectedModel: `${model.provider}/${model.model}` }));
                setShowModelPopup(false);
              }}
              className={classNames(
                'w-full flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                taskInput.selectedModel === `${model.provider}/${model.model}`
                  ? 'bg-emerald-500/20 border border-emerald-500/30'
                  : 'bg-gray-900/50 hover:bg-gray-800'
              )}
            >
              <div>
                <p className="text-sm font-medium text-white">{model.name}</p>
                <p className="text-xs text-gray-500">{model.provider}</p>
              </div>
              {taskInput.selectedModel === `${model.provider}/${model.model}` && (
                <Check className="w-5 h-5 text-emerald-400" />
              )}
            </button>
          ))}
        </div>
      </Popup>

      {/* Agent Selection Popup */}
      <Popup title="Select Agents" isOpen={showAgentPopup} onClose={() => setShowAgentPopup(false)}>
        <div className="space-y-2">
          {availableAgents.map((agent: { id: string; name: string; description: string }) => {
            const isSelected = taskInput.selectedAgents.includes(agent.id);
            return (
              <button
                key={agent.id}
                onClick={() => {
                  setTaskInput((p) => ({
                    ...p,
                    selectedAgents: isSelected
                      ? p.selectedAgents.filter((a) => a !== agent.id)
                      : [...p.selectedAgents, agent.id],
                  }));
                }}
                className={classNames(
                  'w-full flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                  isSelected ? 'bg-purple-500/20 border border-purple-500/30' : 'bg-gray-900/50 hover:bg-gray-800'
                )}
              >
                <div>
                  <p className="text-sm font-medium text-white">{agent.name}</p>
                  <p className="text-xs text-gray-500">{agent.description}</p>
                </div>
                {isSelected && <Check className="w-5 h-5 text-purple-400" />}
              </button>
            );
          })}
        </div>
      </Popup>

      {/* Plugin Selection Popup */}
      <Popup title="Enable Plugins" isOpen={showPluginPopup} onClose={() => setShowPluginPopup(false)}>
        <div className="space-y-4">
          {Object.entries(pluginCategories).map(([category, plugins]) => (
            <div key={category}>
              <h4 className="text-xs font-medium text-gray-400 uppercase mb-2">{category}</h4>
              <div className="space-y-1">
                {plugins.map((plugin) => {
                  const isEnabled = taskInput.enabledPlugins.includes(plugin.id);
                  return (
                    <button
                      key={plugin.id}
                      onClick={() => {
                        setTaskInput((p) => ({
                          ...p,
                          enabledPlugins: isEnabled
                            ? p.enabledPlugins.filter((a) => a !== plugin.id)
                            : [...p.enabledPlugins, plugin.id],
                        }));
                      }}
                      className={classNames(
                        'w-full flex items-center justify-between p-2 rounded-lg transition-colors text-left',
                        isEnabled ? 'bg-amber-500/20 border border-amber-500/30' : 'bg-gray-900/50 hover:bg-gray-800'
                      )}
                    >
                      <span className="text-sm text-white">{plugin.name}</span>
                      {isEnabled && <Check className="w-4 h-4 text-amber-400" />}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Popup>

      {/* Task Type Popup */}
      <Popup title="Select Task Complexity" isOpen={showTaskTypePopup} onClose={() => setShowTaskTypePopup(false)}>
        <div className="space-y-2">
          {taskTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => {
                setTaskInput((p) => ({ ...p, taskType: type.id as 'low' | 'medium' | 'high' }));
                setShowTaskTypePopup(false);
              }}
              className={classNames(
                'w-full flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                taskInput.taskType === type.id
                  ? `bg-${type.color}-500/20 border border-${type.color}-500/30`
                  : 'bg-gray-900/50 hover:bg-gray-800'
              )}
            >
              <div>
                <p className="text-sm font-medium text-white">{type.name}</p>
                <p className="text-xs text-gray-500">{type.description}</p>
              </div>
              {taskInput.taskType === type.id && (
                <Check className={`w-5 h-5 text-${type.color}-400`} />
              )}
            </button>
          ))}
        </div>
      </Popup>

      {/* Stats Popups */}
      <StatsPopup
        isOpen={showStatsPopup === 'episodes'}
        onClose={() => setShowStatsPopup(null)}
        stats={episodeStats}
        title="Episode Statistics"
      />
      <StatsPopup
        isOpen={showStatsPopup === 'steps'}
        onClose={() => setShowStatsPopup(null)}
        stats={stepStats}
        title="Step Statistics"
      />
      <StatsPopup
        isOpen={showStatsPopup === 'reward'}
        onClose={() => setShowStatsPopup(null)}
        stats={rewardStats}
        title="Reward Statistics"
      />
    </div>
  );
};

export default Dashboard;
