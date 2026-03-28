import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  Zap,
  Target,
  TrendingUp,
  Database,
  Cpu,
  Globe,
  Play,
  Pause,
  ChevronDown,
  ChevronRight,
  Terminal,
  Wrench,
  Plug,
  Eye,
  Bot,
  X,
  Check,
  Layers,
  FileText,
  Plus,
  Info,
  Link,
  MessageSquare,
  Image,
  FolderOpen,
  Trash2,
  AlertCircle,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { classNames } from '@/utils/helpers';
import { apiClient } from '@/api/client';

// Types
interface TaskInput {
  urls: string[];
  instruction: string;
  outputInstruction: string;
  taskType: 'low' | 'medium' | 'high';
  selectedModel: string;
  selectedVisionModel: string;
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

interface Asset {
  id: string;
  type: 'url' | 'image' | 'file' | 'data';
  name: string;
  source: 'user' | 'ai';
  content: string;
  timestamp: string;
}

interface MemoryEntry {
  id: string;
  type: 'short_term' | 'working' | 'long_term' | 'shared';
  content: string;
  timestamp: string;
}

interface PluginInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  installed: boolean;
}

interface AgentInfo {
  type: string;
  name: string;
  description: string;
}

interface ModelInfo {
  provider: string;
  model: string;
  name: string;
  description?: string;
}

// View type
type ViewType = 'input' | 'dashboard';

// Info Popup Component
const InfoPopup: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description: string;
  details?: Record<string, string>;
}> = ({ isOpen, onClose, title, description, details }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-gray-800 border border-gray-600 rounded-xl shadow-2xl w-full max-w-md p-5">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Info className="w-5 h-5 text-cyan-400" />
            </div>
            <h3 className="font-semibold text-white text-lg">{title}</h3>
          </div>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-gray-300 text-sm mb-4">{description}</p>
        {details && (
          <div className="space-y-2 pt-3 border-t border-gray-700">
            {Object.entries(details).map(([key, value]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-gray-500">{key}</span>
                <span className="text-gray-300">{value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// Popup Components
interface PopupProps {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

const Popup: React.FC<PopupProps> = ({ title, isOpen, onClose, children, size = 'md' }) => {
  if (!isOpen) return null;
  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className={`bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-full ${sizeClasses[size]} max-h-[80vh] overflow-hidden`}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <h3 className="font-semibold text-white">{title}</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 overflow-y-auto max-h-[65vh]">{children}</div>
      </div>
    </div>
  );
};

// Accordion Component for sidebar
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
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-800/50 hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${color}`} />
          <span className="text-xs font-medium text-white">{title}</span>
          {badge !== undefined && Number(badge) > 0 && (
            <Badge variant="neutral" size="sm">{badge}</Badge>
          )}
        </div>
        {isOpen ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
      </button>
      {isOpen && <div className="p-2 bg-gray-900/30 border-t border-gray-700/50 space-y-1">{children}</div>}
    </div>
  );
};

// Main Dashboard Component
export const Dashboard: React.FC = () => {
  // View state - 'input' or 'dashboard'
  const [currentView, setCurrentView] = useState<ViewType>('input');
  
  // Task input state
  const [taskInput, setTaskInput] = useState<TaskInput>({
    urls: [],
    instruction: '',
    outputInstruction: '',
    taskType: 'medium',
    selectedModel: 'groq/gpt-oss-120b',
    selectedVisionModel: '',
    selectedAgents: [],
    enabledPlugins: [],
  });
  
  // URL input for adding
  const [newUrl, setNewUrl] = useState('');
  
  // Logs
  const [logs, setLogs] = useState<LogEntry[]>([]);
  
  // Running state
  const [isRunning, setIsRunning] = useState(false);
  
  // Assets
  const [assets, setAssets] = useState<Asset[]>([]);
  
  // Memories
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [newMemory, setNewMemory] = useState('');
  
  // Popup states
  const [showModelPopup, setShowModelPopup] = useState(false);
  const [showVisionPopup, setShowVisionPopup] = useState(false);
  const [showAgentPopup, setShowAgentPopup] = useState(false);
  const [showPluginPopup, setShowPluginPopup] = useState(false);
  const [showTaskTypePopup, setShowTaskTypePopup] = useState(false);
  const [showMemoriesPopup, setShowMemoriesPopup] = useState(false);
  const [showAssetsPopup, setShowAssetsPopup] = useState(false);
  
  // Info popup
  const [infoPopup, setInfoPopup] = useState<{ isOpen: boolean; title: string; description: string; details?: Record<string, string> }>({
    isOpen: false,
    title: '',
    description: '',
  });

  // Episode stats - session-based, start at 0
  const [stats, setStats] = useState({ episodes: 0, steps: 0, totalReward: 0, avgReward: 0 });

  // API Queries
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.healthCheck(),
    refetchInterval: 5000,
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const res = await fetch('/api/agents/list');
      if (!res.ok) return { agent_types: [] };
      return res.json();
    },
  });

  const { data: pluginsData } = useQuery({
    queryKey: ['plugins'],
    queryFn: async () => {
      const res = await fetch('/api/plugins');
      if (!res.ok) return { plugins: {} };
      return res.json();
    },
  });

  const { data: memoryData } = useQuery({
    queryKey: ['memory-stats'],
    queryFn: async () => {
      const res = await fetch('/api/memory/stats/overview');
      if (!res.ok) return { total_count: 0 };
      return res.json();
    },
    refetchInterval: 3000,
  });

  const { data: settingsData } = useQuery({
    queryKey: ['client-settings'],
    queryFn: async () => {
      const res = await fetch('/api/settings');
      if (!res.ok) return { available_models: [], api_keys_configured: {} };
      return res.json();
    },
  });

  // Get installed plugins only
  const getInstalledPlugins = () => {
    if (!pluginsData?.plugins) return { mcps: [], skills: [], apis: [], processors: [] };
    const result: Record<string, PluginInfo[]> = {};
    for (const [category, plugins] of Object.entries(pluginsData.plugins)) {
      result[category] = (plugins as PluginInfo[]).filter(p => p.installed);
    }
    return result;
  };

  const installedPlugins = getInstalledPlugins();
  
  // Get agents
  const agents: AgentInfo[] = agentsData?.agent_types || [];
  
  // Get models grouped by provider
  const modelsByProvider = (): Record<string, ModelInfo[]> => {
    const models = settingsData?.available_models || [];
    const grouped: Record<string, ModelInfo[]> = {};
    models.forEach((m: ModelInfo) => {
      if (!grouped[m.provider]) grouped[m.provider] = [];
      grouped[m.provider].push(m);
    });
    return grouped;
  };

  // Vision models
  const visionModels: ModelInfo[] = [
    { provider: 'openai', model: 'gpt-4-vision-preview', name: 'GPT-4 Vision', description: 'OpenAI vision model' },
    { provider: 'google', model: 'gemini-pro-vision', name: 'Gemini Pro Vision', description: 'Google vision model' },
    { provider: 'anthropic', model: 'claude-3-opus-vision', name: 'Claude 3 Vision', description: 'Anthropic vision model' },
  ];

  // Task types
  const taskTypes = [
    { id: 'low', name: 'Low', description: 'Simple single-page extraction', color: 'emerald', icon: '🟢' },
    { id: 'medium', name: 'Medium', description: 'Multi-page navigation', color: 'amber', icon: '🟡' },
    { id: 'high', name: 'High', description: 'Complex interactive tasks', color: 'red', icon: '🔴' },
  ];

  // Add URL to list
  const handleAddUrl = () => {
    if (newUrl.trim() && !taskInput.urls.includes(newUrl.trim())) {
      const url = newUrl.trim();
      setTaskInput(p => ({ ...p, urls: [...p.urls, url] }));
      // Also add to assets
      setAssets(prev => [...prev, {
        id: Date.now().toString(),
        type: 'url',
        name: url,
        source: 'user',
        content: url,
        timestamp: new Date().toISOString(),
      }]);
      setNewUrl('');
    }
  };

  // Remove URL
  const handleRemoveUrl = (url: string) => {
    setTaskInput(p => ({ ...p, urls: p.urls.filter(u => u !== url) }));
    setAssets(prev => prev.filter(a => a.content !== url));
  };

  // Add memory
  const handleAddMemory = () => {
    if (newMemory.trim()) {
      setMemories(prev => [...prev, {
        id: Date.now().toString(),
        type: 'working',
        content: newMemory.trim(),
        timestamp: new Date().toISOString(),
      }]);
      setNewMemory('');
    }
  };

  // Start task
  const handleStart = () => {
    if (taskInput.urls.length === 0 && !taskInput.instruction) return;
    
    setIsRunning(true);
    setCurrentView('dashboard');
    
    // Add initial log
    setLogs(prev => [...prev, {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `Starting episode with ${taskInput.urls.length} URLs`,
      source: 'system',
    }]);
    
    // Update stats
    setStats(prev => ({ ...prev, episodes: prev.episodes + 1 }));
  };

  // Stop task
  const handleStop = () => {
    setIsRunning(false);
    setLogs(prev => [...prev, {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      level: 'warn',
      message: 'Episode stopped by user',
      source: 'system',
    }]);
  };

  // Format time
  const formatTime = (isoString: string) => {
    return new Date(isoString).toLocaleTimeString('en-US', { hour12: false });
  };

  // Log level colors
  const getLogLevelColor = (level: LogEntry['level']) => {
    const colors = { info: 'text-cyan-400', warn: 'text-amber-400', error: 'text-red-400', debug: 'text-gray-400' };
    return colors[level];
  };

  // Check system status
  const isSystemOnline = health?.status === 'healthy';

  // Show info popup
  const showInfo = (title: string, description: string, details?: Record<string, string>) => {
    setInfoPopup({ isOpen: true, title, description, details });
  };

  // ========== INPUT VIEW ==========
  if (currentView === 'input') {
    return (
      <div className="h-[calc(100vh-64px)] flex flex-col bg-gray-900">
        {/* System Status Banner */}
        {!isSystemOnline && (
          <div className="flex-shrink-0 px-4 py-2 bg-red-500/20 border-b border-red-500/30 flex items-center justify-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm text-red-400">System is offline. Please check your connection.</span>
          </div>
        )}
        
        {/* Main Content - ChatGPT-like interface */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 overflow-auto">
          <div className="w-full max-w-3xl space-y-6">
            {/* Header */}
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-white mb-2">ScrapeRL</h1>
              <p className="text-gray-400">Enter your scraping task below</p>
            </div>

            {/* URLs Section */}
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Link className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-medium text-white">Target URLs</span>
              </div>
              
              {/* URL Input */}
              <div className="flex gap-2 mb-3">
                <input
                  type="url"
                  placeholder="https://example.com/page-to-scrape"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddUrl()}
                  className="flex-1 px-4 py-2.5 bg-gray-900/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                />
                <button
                  onClick={handleAddUrl}
                  className="px-4 py-2.5 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 text-cyan-400 rounded-lg transition-colors"
                >
                  <Plus className="w-5 h-5" />
                </button>
              </div>
              
              {/* URL List */}
              {taskInput.urls.length > 0 && (
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {taskInput.urls.map((url, idx) => (
                    <div key={idx} className="flex items-center justify-between px-3 py-2 bg-gray-900/50 rounded-lg">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <Globe className="w-4 h-4 text-gray-500 flex-shrink-0" />
                        <span className="text-sm text-gray-300 truncate">{url}</span>
                      </div>
                      <button onClick={() => handleRemoveUrl(url)} className="p-1 text-gray-500 hover:text-red-400">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Instructions */}
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <MessageSquare className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium text-white">Instructions</span>
              </div>
              <textarea
                placeholder="What data do you want to extract? Be specific about the fields and structure..."
                value={taskInput.instruction}
                onChange={(e) => setTaskInput(p => ({ ...p, instruction: e.target.value }))}
                rows={3}
                className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none"
              />
            </div>

            {/* Output Instructions */}
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium text-white">Output Format</span>
              </div>
              <textarea
                placeholder="How should the output be formatted? (e.g., JSON with fields: name, price, description)"
                value={taskInput.outputInstruction}
                onChange={(e) => setTaskInput(p => ({ ...p, outputInstruction: e.target.value }))}
                rows={2}
                className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
              />
            </div>

            {/* Configuration Options */}
            <div className="flex flex-wrap items-center justify-center gap-3">
              {/* Model */}
              <button
                onClick={() => setShowModelPopup(true)}
                className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                <Cpu className="w-4 h-4" />
                {taskInput.selectedModel ? taskInput.selectedModel.split('/')[1] : 'Model'}
              </button>
              
              {/* Vision */}
              <button
                onClick={() => setShowVisionPopup(true)}
                className={classNames(
                  'px-4 py-2 border rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
                  taskInput.selectedVisionModel 
                    ? 'bg-pink-500/10 border-pink-500/30 text-pink-400' 
                    : 'bg-gray-700/50 border-gray-600 text-gray-400 hover:border-pink-500/30 hover:text-pink-400'
                )}
              >
                <Eye className="w-4 h-4" />
                {taskInput.selectedVisionModel ? 'Vision ✓' : 'Vision'}
              </button>
              
              {/* Agents */}
              <button
                onClick={() => setShowAgentPopup(true)}
                className="px-4 py-2 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                <Bot className="w-4 h-4" />
                Agents {taskInput.selectedAgents.length > 0 && `(${taskInput.selectedAgents.length})`}
              </button>
              
              {/* Plugins */}
              <button
                onClick={() => setShowPluginPopup(true)}
                className="px-4 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                <Plug className="w-4 h-4" />
                Plugins {taskInput.enabledPlugins.length > 0 && `(${taskInput.enabledPlugins.length})`}
              </button>
              
              {/* Task Type */}
              <button
                onClick={() => setShowTaskTypePopup(true)}
                className={classNames(
                  'px-4 py-2 border rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
                  taskInput.taskType === 'low' && 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
                  taskInput.taskType === 'medium' && 'bg-amber-500/10 border-amber-500/30 text-amber-400',
                  taskInput.taskType === 'high' && 'bg-red-500/10 border-red-500/30 text-red-400'
                )}
              >
                <Target className="w-4 h-4" />
                {taskTypes.find(t => t.id === taskInput.taskType)?.icon} {taskInput.taskType.charAt(0).toUpperCase() + taskInput.taskType.slice(1)}
              </button>
            </div>

            {/* Start Button */}
            <div className="flex justify-center pt-4">
              <button
                onClick={handleStart}
                disabled={taskInput.urls.length === 0 || !isSystemOnline}
                className="px-8 py-3 bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors flex items-center gap-3 shadow-lg shadow-emerald-500/20"
              >
                <Play className="w-5 h-5" />
                Start Scraping
              </button>
            </div>
          </div>
        </div>

        {/* Popups */}
        {renderPopups()}
      </div>
    );
  }

  // ========== DASHBOARD VIEW ==========
  // Helper function to render popups (used in both views)
  function renderPopups() {
    return (
      <>
        {/* Model Selection Popup */}
        <Popup title="Select Model" isOpen={showModelPopup} onClose={() => setShowModelPopup(false)} size="lg">
          <div className="space-y-4">
            {Object.entries(modelsByProvider()).map(([provider, models]) => (
              <div key={provider}>
                <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-cyan-400"></div>
                  {provider}
                </h4>
                <div className="space-y-1 pl-4">
                  {models.map((model) => (
                    <button
                      key={`${model.provider}/${model.model}`}
                      onClick={() => {
                        setTaskInput(p => ({ ...p, selectedModel: `${model.provider}/${model.model}` }));
                        setShowModelPopup(false);
                      }}
                      className={classNames(
                        'w-full flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                        taskInput.selectedModel === `${model.provider}/${model.model}`
                          ? 'bg-cyan-500/20 border border-cyan-500/30'
                          : 'bg-gray-900/50 hover:bg-gray-800'
                      )}
                    >
                      <div>
                        <p className="text-sm font-medium text-white">{model.name}</p>
                        <p className="text-xs text-gray-500">{model.description || model.model}</p>
                      </div>
                      {taskInput.selectedModel === `${model.provider}/${model.model}` && (
                        <Check className="w-5 h-5 text-cyan-400" />
                      )}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Popup>

        {/* Vision Model Popup */}
        <Popup title="Select Vision Model" isOpen={showVisionPopup} onClose={() => setShowVisionPopup(false)}>
          <div className="space-y-2">
            <button
              onClick={() => {
                setTaskInput(p => ({ ...p, selectedVisionModel: '' }));
                setShowVisionPopup(false);
              }}
              className={classNames(
                'w-full flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                !taskInput.selectedVisionModel ? 'bg-gray-700/50 border border-gray-600' : 'bg-gray-900/50 hover:bg-gray-800'
              )}
            >
              <span className="text-sm text-gray-400">None (No vision)</span>
              {!taskInput.selectedVisionModel && <Check className="w-5 h-5 text-gray-400" />}
            </button>
            {visionModels.map((model) => (
              <div key={model.model} className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setTaskInput(p => ({ ...p, selectedVisionModel: model.model }));
                    setShowVisionPopup(false);
                  }}
                  className={classNames(
                    'flex-1 flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                    taskInput.selectedVisionModel === model.model
                      ? 'bg-pink-500/20 border border-pink-500/30'
                      : 'bg-gray-900/50 hover:bg-gray-800'
                  )}
                >
                  <div>
                    <p className="text-sm font-medium text-white">{model.name}</p>
                    <p className="text-xs text-gray-500">{model.provider}</p>
                  </div>
                  {taskInput.selectedVisionModel === model.model && <Check className="w-5 h-5 text-pink-400" />}
                </button>
                <button
                  onClick={() => showInfo(model.name, model.description || 'Vision model for image understanding', { Provider: model.provider, Model: model.model })}
                  className="p-2 text-gray-500 hover:text-gray-300"
                >
                  <Info className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </Popup>

        {/* Agent Selection Popup */}
        <Popup title="Select Agents" isOpen={showAgentPopup} onClose={() => setShowAgentPopup(false)}>
          <div className="space-y-2">
            {agents.map((agent) => {
              const isSelected = taskInput.selectedAgents.includes(agent.type);
              return (
                <div key={agent.type} className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setTaskInput(p => ({
                        ...p,
                        selectedAgents: isSelected
                          ? p.selectedAgents.filter(a => a !== agent.type)
                          : [...p.selectedAgents, agent.type],
                      }));
                    }}
                    className={classNames(
                      'flex-1 flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                      isSelected ? 'bg-purple-500/20 border border-purple-500/30' : 'bg-gray-900/50 hover:bg-gray-800'
                    )}
                  >
                    <div>
                      <p className="text-sm font-medium text-white">{agent.name}</p>
                      <p className="text-xs text-gray-500">{agent.description}</p>
                    </div>
                    {isSelected && <Check className="w-5 h-5 text-purple-400" />}
                  </button>
                  <button
                    onClick={() => showInfo(agent.name, agent.description, { Type: agent.type })}
                    className="p-2 text-gray-500 hover:text-gray-300"
                  >
                    <Info className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        </Popup>

        {/* Plugin Selection Popup */}
        <Popup title="Enable Plugins" isOpen={showPluginPopup} onClose={() => setShowPluginPopup(false)} size="lg">
          <div className="space-y-4">
            {Object.entries(installedPlugins).map(([category, plugins]) => {
              if (plugins.length === 0) return null;
              return (
                <div key={category}>
                  <h4 className="text-xs font-semibold text-gray-400 uppercase mb-2">{category}</h4>
                  <div className="space-y-1">
                    {plugins.map((plugin: PluginInfo) => {
                      const isEnabled = taskInput.enabledPlugins.includes(plugin.id);
                      return (
                        <div key={plugin.id} className="flex items-center gap-2">
                          <button
                            onClick={() => {
                              setTaskInput(p => ({
                                ...p,
                                enabledPlugins: isEnabled
                                  ? p.enabledPlugins.filter(a => a !== plugin.id)
                                  : [...p.enabledPlugins, plugin.id],
                              }));
                            }}
                            className={classNames(
                              'flex-1 flex items-center justify-between p-2 rounded-lg transition-colors text-left',
                              isEnabled ? 'bg-amber-500/20 border border-amber-500/30' : 'bg-gray-900/50 hover:bg-gray-800'
                            )}
                          >
                            <span className="text-sm text-white">{plugin.name}</span>
                            {isEnabled && <Check className="w-4 h-4 text-amber-400" />}
                          </button>
                          <button
                            onClick={() => showInfo(plugin.name, plugin.description, { Category: plugin.category, ID: plugin.id })}
                            className="p-2 text-gray-500 hover:text-gray-300"
                          >
                            <Info className="w-4 h-4" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </Popup>

        {/* Task Type Popup */}
        <Popup title="Select Task Complexity" isOpen={showTaskTypePopup} onClose={() => setShowTaskTypePopup(false)}>
          <div className="space-y-2">
            {taskTypes.map((type) => (
              <button
                key={type.id}
                onClick={() => {
                  setTaskInput(p => ({ ...p, taskType: type.id as 'low' | 'medium' | 'high' }));
                  setShowTaskTypePopup(false);
                }}
                className={classNames(
                  'w-full flex items-center justify-between p-3 rounded-lg transition-colors text-left',
                  taskInput.taskType === type.id
                    ? type.id === 'low' ? 'bg-emerald-500/20 border border-emerald-500/30'
                    : type.id === 'medium' ? 'bg-amber-500/20 border border-amber-500/30'
                    : 'bg-red-500/20 border border-red-500/30'
                    : 'bg-gray-900/50 hover:bg-gray-800'
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl">{type.icon}</span>
                  <div>
                    <p className="text-sm font-medium text-white">{type.name}</p>
                    <p className="text-xs text-gray-500">{type.description}</p>
                  </div>
                </div>
                {taskInput.taskType === type.id && (
                  <Check className={classNames(
                    'w-5 h-5',
                    type.id === 'low' ? 'text-emerald-400' : type.id === 'medium' ? 'text-amber-400' : 'text-red-400'
                  )} />
                )}
              </button>
            ))}
          </div>
        </Popup>

        {/* Memories Popup */}
        <Popup title="Memories" isOpen={showMemoriesPopup} onClose={() => setShowMemoriesPopup(false)} size="lg">
          <div className="space-y-3">
            {/* Add Memory */}
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Add a new memory..."
                value={newMemory}
                onChange={(e) => setNewMemory(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddMemory()}
                className="flex-1 px-3 py-2 bg-gray-900/50 border border-gray-700 rounded-lg text-white text-sm"
              />
              <button onClick={handleAddMemory} className="px-3 py-2 bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg">
                <Plus className="w-4 h-4" />
              </button>
            </div>
            
            {/* Memory List */}
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {memories.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">No memories yet</div>
              ) : (
                memories.map((mem) => (
                  <div key={mem.id} className="p-3 bg-gray-900/50 rounded-lg">
                    <div className="flex items-start justify-between">
                      <p className="text-sm text-gray-300 flex-1">{mem.content}</p>
                      <button
                        onClick={() => setMemories(prev => prev.filter(m => m.id !== mem.id))}
                        className="p-1 text-gray-500 hover:text-red-400 ml-2"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="neutral" size="sm">{mem.type}</Badge>
                      <span className="text-[10px] text-gray-500">{formatTime(mem.timestamp)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </Popup>

        {/* Assets Popup */}
        <Popup title="Assets" isOpen={showAssetsPopup} onClose={() => setShowAssetsPopup(false)} size="lg">
          <div className="space-y-3">
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {assets.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">No assets yet. URLs and fetched data will appear here.</div>
              ) : (
                assets.map((asset) => (
                  <div key={asset.id} className="p-3 bg-gray-900/50 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        {asset.type === 'url' && <Link className="w-4 h-4 text-cyan-400 flex-shrink-0" />}
                        {asset.type === 'image' && <Image className="w-4 h-4 text-pink-400 flex-shrink-0" />}
                        {asset.type === 'file' && <FileText className="w-4 h-4 text-amber-400 flex-shrink-0" />}
                        {asset.type === 'data' && <Database className="w-4 h-4 text-emerald-400 flex-shrink-0" />}
                        <span className="text-sm text-gray-300 truncate">{asset.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={asset.source === 'ai' ? 'info' : 'neutral'} size="sm">{asset.source}</Badge>
                        <button
                          onClick={() => setAssets(prev => prev.filter(a => a.id !== asset.id))}
                          className="p-1 text-gray-500 hover:text-red-400"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </Popup>

        {/* Info Popup */}
        <InfoPopup
          isOpen={infoPopup.isOpen}
          onClose={() => setInfoPopup({ ...infoPopup, isOpen: false })}
          title={infoPopup.title}
          description={infoPopup.description}
          details={infoPopup.details}
        />
      </>
    );
  }

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col">
      {/* Main 3-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Active Components */}
        <div className="w-56 flex-shrink-0 bg-gray-800/30 border-r border-gray-700/50 overflow-y-auto p-2 space-y-2">
          {/* Back to Input */}
          <button
            onClick={() => setCurrentView('input')}
            className="w-full flex items-center gap-2 px-3 py-2 bg-gray-700/50 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition-colors"
          >
            <ChevronRight className="w-4 h-4 rotate-180" />
            New Task
          </button>

          {/* Agents */}
          <Accordion title="Agents" icon={Bot} badge={taskInput.selectedAgents.length} color="text-purple-400" defaultOpen>
            {taskInput.selectedAgents.length === 0 ? (
              <p className="text-xs text-gray-500 p-2">No agents selected</p>
            ) : (
              taskInput.selectedAgents.map((agentId) => {
                const agent = agents.find(a => a.type === agentId);
                return (
                  <div key={agentId} className="flex items-center justify-between p-2 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
                      <span className="text-xs text-white">{agent?.name || agentId}</span>
                    </div>
                    <button onClick={() => showInfo(agent?.name || agentId, agent?.description || '', { Type: agentId })} className="text-gray-500 hover:text-gray-300">
                      <Info className="w-3 h-3" />
                    </button>
                  </div>
                );
              })
            )}
          </Accordion>

          {/* MCPs */}
          <Accordion title="MCPs" icon={Wrench} badge={taskInput.enabledPlugins.filter(p => installedPlugins.mcps?.some((m: PluginInfo) => m.id === p)).length} color="text-amber-400">
            {installedPlugins.mcps?.filter((p: PluginInfo) => taskInput.enabledPlugins.includes(p.id)).map((plugin: PluginInfo) => (
              <div key={plugin.id} className="flex items-center justify-between p-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                <span className="text-xs text-white">{plugin.name}</span>
                <button onClick={() => showInfo(plugin.name, plugin.description)} className="text-gray-500 hover:text-gray-300">
                  <Info className="w-3 h-3" />
                </button>
              </div>
            ))}
            {!installedPlugins.mcps?.some((p: PluginInfo) => taskInput.enabledPlugins.includes(p.id)) && (
              <p className="text-xs text-gray-500 p-2">No MCPs enabled</p>
            )}
          </Accordion>

          {/* Skills */}
          <Accordion title="Skills" icon={Zap} badge={taskInput.enabledPlugins.filter(p => installedPlugins.skills?.some((s: PluginInfo) => s.id === p)).length} color="text-cyan-400">
            {installedPlugins.skills?.filter((p: PluginInfo) => taskInput.enabledPlugins.includes(p.id)).map((plugin: PluginInfo) => (
              <div key={plugin.id} className="flex items-center justify-between p-2 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
                <span className="text-xs text-white">{plugin.name}</span>
                <button onClick={() => showInfo(plugin.name, plugin.description)} className="text-gray-500 hover:text-gray-300">
                  <Info className="w-3 h-3" />
                </button>
              </div>
            ))}
            {!installedPlugins.skills?.some((p: PluginInfo) => taskInput.enabledPlugins.includes(p.id)) && (
              <p className="text-xs text-gray-500 p-2">No skills enabled</p>
            )}
          </Accordion>

          {/* APIs */}
          <Accordion title="APIs" icon={Plug} badge={taskInput.enabledPlugins.filter(p => installedPlugins.apis?.some((a: PluginInfo) => a.id === p)).length} color="text-emerald-400">
            {installedPlugins.apis?.filter((p: PluginInfo) => taskInput.enabledPlugins.includes(p.id)).map((plugin: PluginInfo) => (
              <div key={plugin.id} className="flex items-center justify-between p-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                <span className="text-xs text-white">{plugin.name}</span>
                <button onClick={() => showInfo(plugin.name, plugin.description)} className="text-gray-500 hover:text-gray-300">
                  <Info className="w-3 h-3" />
                </button>
              </div>
            ))}
            {!installedPlugins.apis?.some((p: PluginInfo) => taskInput.enabledPlugins.includes(p.id)) && (
              <p className="text-xs text-gray-500 p-2">No APIs enabled</p>
            )}
          </Accordion>

          {/* Vision */}
          <Accordion title="Vision" icon={Eye} badge={taskInput.selectedVisionModel ? 1 : 0} color="text-pink-400">
            {taskInput.selectedVisionModel ? (
              <div className="p-2 bg-pink-500/10 border border-pink-500/30 rounded-lg">
                <span className="text-xs text-white">{taskInput.selectedVisionModel}</span>
              </div>
            ) : (
              <p className="text-xs text-gray-500 p-2">No vision model</p>
            )}
          </Accordion>

          {/* System Status */}
          <div className="mt-4 p-3 bg-gray-900/50 border border-gray-700/50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">Status</span>
              <Badge variant={isSystemOnline ? 'success' : 'error'} size="sm">
                {isSystemOnline ? 'Online' : 'Offline'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">Model</span>
              <span className="text-xs text-gray-300">{taskInput.selectedModel.split('/')[1]}</span>
            </div>
          </div>
        </div>

        {/* Center Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Stats Header - Session-based, start at 0 */}
          <div className="flex-shrink-0 p-3 bg-gray-800/30 border-b border-gray-700/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-emerald-500/20 rounded">
                    <Layers className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white">{stats.episodes}</p>
                    <p className="text-[10px] text-gray-500">Episodes</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-cyan-500/20 rounded">
                    <Target className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white">{stats.steps}</p>
                    <p className="text-[10px] text-gray-500">Steps</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-purple-500/20 rounded">
                    <TrendingUp className="w-4 h-4 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white">{stats.avgReward.toFixed(1)}</p>
                    <p className="text-[10px] text-gray-500">Avg Reward</p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-sm font-mono text-white">{new Date().toLocaleTimeString()}</p>
                  <p className="text-[10px] text-gray-500">Current Time</p>
                </div>
                
                {/* Control Buttons */}
                {isRunning ? (
                  <button
                    onClick={handleStop}
                    className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                  >
                    <Pause className="w-4 h-4" />
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={handleStart}
                    disabled={taskInput.urls.length === 0}
                    className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                  >
                    <Play className="w-4 h-4" />
                    Start
                  </button>
                )}
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
                      <p className="text-sm text-gray-300">Processing URLs...</p>
                      <p className="text-xs text-gray-500 mt-1">Agent: {taskInput.selectedAgents[0] || 'None'} | URLs: {taskInput.urls.length}</p>
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
  "urls": ${JSON.stringify(taskInput.urls.slice(0, 3))},
  "instruction": "${taskInput.instruction.slice(0, 50)}...",
  "status": "processing",
  "elements": [],
  "extracted_data": []
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
                    {taskInput.urls.length} URLs loaded. Click Start to begin scraping.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Logs Terminal */}
          <div className="flex-shrink-0 h-32 bg-gray-900 border-t border-gray-700/50">
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-gray-500" />
                <span className="text-xs font-medium text-gray-400">Logs</span>
              </div>
              <button onClick={() => setLogs([])} className="text-xs text-gray-500 hover:text-gray-300">
                Clear
              </button>
            </div>
            <div className="h-[calc(100%-28px)] overflow-y-auto p-2 font-mono text-xs">
              {logs.length === 0 ? (
                <p className="text-gray-600 p-2">No logs yet...</p>
              ) : (
                logs.map((log) => (
                  <div key={log.id} className="flex items-start gap-2 py-0.5">
                    <span className="text-gray-600">[{formatTime(log.timestamp)}]</span>
                    <span className={getLogLevelColor(log.level)}>[{log.level.toUpperCase()}]</span>
                    {log.source && <span className="text-purple-400">[{log.source}]</span>}
                    <span className="text-gray-300">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="w-64 flex-shrink-0 bg-gray-800/30 border-l border-gray-700/50 overflow-y-auto p-3 space-y-3">
          {/* Input Summary */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-medium text-white">Input</span>
              </div>
              <button
                onClick={() => setCurrentView('input')}
                className="text-xs text-cyan-400 hover:text-cyan-300"
              >
                Edit
              </button>
            </div>
            <div className="space-y-2 text-xs">
              <div>
                <p className="text-gray-500">URLs ({taskInput.urls.length})</p>
                <p className="text-gray-300 truncate">{taskInput.urls[0] || 'None'}</p>
              </div>
              <div>
                <p className="text-gray-500">Instruction</p>
                <p className="text-gray-300 truncate">{taskInput.instruction || 'None'}</p>
              </div>
            </div>
          </div>

          {/* Memories */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium text-white">Memories</span>
              </div>
              <button onClick={() => setShowMemoriesPopup(true)} className="text-xs text-purple-400 hover:text-purple-300">
                View All
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="p-2 bg-gray-800/50 rounded">
                <p className="text-lg font-bold text-emerald-400">{memoryData?.short_term_count || 0}</p>
                <p className="text-[10px] text-gray-500">Short</p>
              </div>
              <div className="p-2 bg-gray-800/50 rounded">
                <p className="text-lg font-bold text-cyan-400">{memoryData?.working_count || 0}</p>
                <p className="text-[10px] text-gray-500">Working</p>
              </div>
              <div className="p-2 bg-gray-800/50 rounded">
                <p className="text-lg font-bold text-purple-400">{memoryData?.long_term_count || 0}</p>
                <p className="text-[10px] text-gray-500">Long</p>
              </div>
              <div className="p-2 bg-gray-800/50 rounded">
                <p className="text-lg font-bold text-amber-400">{memoryData?.shared_count || 0}</p>
                <p className="text-[10px] text-gray-500">Shared</p>
              </div>
            </div>
            <button
              onClick={() => setShowMemoriesPopup(true)}
              className="w-full mt-2 px-2 py-1.5 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded text-xs flex items-center justify-center gap-1"
            >
              <Plus className="w-3 h-3" /> Add Memory
            </button>
          </div>

          {/* Assets */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-medium text-white">Assets</span>
              </div>
              <Badge variant="neutral" size="sm">{assets.length}</Badge>
            </div>
            
            {assets.length === 0 ? (
              <p className="text-center py-4 text-gray-500 text-xs">No assets yet</p>
            ) : (
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {assets.slice(0, 5).map((asset) => (
                  <div key={asset.id} className="flex items-center justify-between p-2 bg-gray-800/50 rounded text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      {asset.type === 'url' && <Link className="w-3 h-3 text-cyan-400 flex-shrink-0" />}
                      {asset.type === 'data' && <Database className="w-3 h-3 text-emerald-400 flex-shrink-0" />}
                      <span className="text-gray-300 truncate">{asset.name.slice(0, 30)}</span>
                    </div>
                    <Badge variant={asset.source === 'ai' ? 'info' : 'neutral'} size="sm">{asset.source}</Badge>
                  </div>
                ))}
              </div>
            )}
            
            <button
              onClick={() => setShowAssetsPopup(true)}
              className="w-full mt-2 px-2 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded text-xs"
            >
              View All Assets
            </button>
          </div>

          {/* Extracted Data */}
          <div className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium text-white">Extracted Data</span>
              </div>
              <Badge variant="neutral" size="sm">0 items</Badge>
            </div>
            <div className="text-center py-4 text-gray-500 text-xs">
              No data extracted yet.
            </div>
          </div>
        </div>
      </div>

      {/* Popups */}
      {renderPopups()}
    </div>
  );
};

export default Dashboard;
