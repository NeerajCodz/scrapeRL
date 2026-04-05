import React, { useState, useRef, useCallback } from 'react';
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
  Image as ImageIcon,
  FolderOpen,
  Trash2,
  AlertCircle,
  Download,
  Copy,
  Navigation,
  Search,
  Code,
  CheckCircle,
  XCircle,
  Clock,
  FileJson,
  Sparkles,
  Brain,
  Compass,
  Shield,
  type LucideIcon,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { classNames } from '@/utils/helpers';
import { apiClient, type ScrapeStep, type ScrapeResponse, type ScrapeRequest } from '@/api/client';

// Step action to icon mapping
const getStepIcon = (action: string): LucideIcon => {
  const iconMap: Record<string, LucideIcon> = {
    'initialize': Sparkles,
    'navigate': Navigation,
    'extract': Search,
    'plugins': Plug,
    'planner': Brain,
    'planner_python': Code,
    'navigator': Compass,
    'navigator_python': Code,
    'extractor_python': Code,
    'verify': Shield,
    'verifier': Shield,
    'complete': CheckCircle,
    'mcp_search': Search,
    'python_sandbox': Terminal,
    'error': XCircle,
  };
  return iconMap[action] || Activity;
};

// Step action color mapping
const getStepColor = (action: string, status: string): string => {
  if (status === 'failed') return 'text-red-400 bg-red-500/20 border-red-500/30';
  if (status === 'running') return 'text-cyan-400 bg-cyan-500/20 border-cyan-500/30 animate-pulse';
  
  const colorMap: Record<string, string> = {
    'initialize': 'text-purple-400 bg-purple-500/20 border-purple-500/30',
    'navigate': 'text-blue-400 bg-blue-500/20 border-blue-500/30',
    'extract': 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30',
    'plugins': 'text-amber-400 bg-amber-500/20 border-amber-500/30',
    'planner': 'text-pink-400 bg-pink-500/20 border-pink-500/30',
    'planner_python': 'text-orange-400 bg-orange-500/20 border-orange-500/30',
    'navigator': 'text-indigo-400 bg-indigo-500/20 border-indigo-500/30',
    'navigator_python': 'text-orange-400 bg-orange-500/20 border-orange-500/30',
    'extractor_python': 'text-orange-400 bg-orange-500/20 border-orange-500/30',
    'verify': 'text-teal-400 bg-teal-500/20 border-teal-500/30',
    'verifier': 'text-teal-400 bg-teal-500/20 border-teal-500/30',
    'complete': 'text-green-400 bg-green-500/20 border-green-500/30',
    'mcp_search': 'text-cyan-400 bg-cyan-500/20 border-cyan-500/30',
    'python_sandbox': 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30',
  };
  return colorMap[action] || 'text-slate-400 bg-slate-500/20 border-slate-500/30';
};

// Step Accordion Component
interface StepAccordionItemProps {
  step: ScrapeStep;
  isExpanded: boolean;
  onToggle: () => void;
  isLatest: boolean;
}

const StepAccordionItem: React.FC<StepAccordionItemProps> = ({ step, isExpanded, onToggle, isLatest }) => {
  const Icon = getStepIcon(step.action);
  const colorClasses = getStepColor(step.action, step.status);
  
  return (
    <div className={classNames(
      'border rounded-lg overflow-hidden transition-all',
      isLatest ? 'ring-2 ring-cyan-500/50' : '',
      colorClasses.split(' ').slice(1).join(' ')
    )}>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={classNames('p-2 rounded-lg', colorClasses.split(' ').slice(1, 3).join(' '))}>
            <Icon className={classNames('w-4 h-4', colorClasses.split(' ')[0])} />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-white">
                {step.action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </span>
              <Badge 
                variant={step.status === 'completed' ? 'success' : step.status === 'failed' ? 'error' : 'info'} 
                size="sm"
              >
                {step.status}
              </Badge>
            </div>
            <p className="text-xs text-slate-400 truncate max-w-[300px]">{step.message}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-xs text-slate-500">Step {step.step_number}</span>
            {step.reward > 0 && (
              <p className="text-xs text-emerald-400">+{step.reward.toFixed(2)}</p>
            )}
          </div>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>
      
      {isExpanded && (
        <div className="px-4 py-3 border-t border-white/10 bg-slate-900/50 space-y-3">
          {/* Step Details */}
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-slate-500">Action:</span>
              <span className="ml-2 text-slate-300">{step.action}</span>
            </div>
            <div>
              <span className="text-slate-500">Status:</span>
              <span className={classNames(
                'ml-2',
                step.status === 'completed' ? 'text-emerald-400' : 
                step.status === 'failed' ? 'text-red-400' : 'text-cyan-400'
              )}>{step.status}</span>
            </div>
            {step.url && (
              <div className="col-span-2">
                <span className="text-slate-500">URL:</span>
                <span className="ml-2 text-cyan-400 truncate">{step.url}</span>
              </div>
            )}
            {step.duration_ms && (
              <div>
                <span className="text-slate-500">Duration:</span>
                <span className="ml-2 text-slate-300">{step.duration_ms.toFixed(0)}ms</span>
              </div>
            )}
            <div>
              <span className="text-slate-500">Reward:</span>
              <span className="ml-2 text-emerald-400">{step.reward.toFixed(2)}</span>
            </div>
          </div>
          
          {/* Extracted Data */}
          {step.extracted_data && Object.keys(step.extracted_data).length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-slate-500 mb-2">Extracted Data:</p>
              <pre className="text-xs text-slate-300 bg-slate-800/50 rounded-lg p-3 overflow-auto max-h-40 font-mono">
                {JSON.stringify(step.extracted_data, null, 2)}
              </pre>
            </div>
          )}
          
          {/* Timestamp */}
          <div className="flex items-center gap-2 text-[10px] text-slate-600">
            <Clock className="w-3 h-3" />
            {new Date(step.timestamp).toLocaleTimeString()}
          </div>
        </div>
      )}
    </div>
  );
};

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
  
  // Streaming state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<ScrapeStep | null>(null);
  const [allSteps, setAllSteps] = useState<ScrapeStep[]>([]);
  const [expandedStepIndex, setExpandedStepIndex] = useState<number | null>(null);
  const [scrapeResult, setScrapeResult] = useState<ScrapeResponse | null>(null);
  const [progress, setProgress] = useState({ urlIndex: 0, totalUrls: 0, currentUrl: '' });
  const [extractedData, setExtractedData] = useState<Record<string, unknown>>({});
  const abortControllerRef = useRef<{ abort: () => void } | null>(null);
  
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

  const detectOutputFormat = (outputInstruction: string): ScrapeRequest['output_format'] => {
    const normalized = outputInstruction.toLowerCase();
    if (normalized.includes('csv')) return 'csv';
    if (normalized.includes('markdown') || normalized.includes('md')) return 'markdown';
    if (normalized.includes('text') || normalized.includes('plain')) return 'text';
    return 'json';
  };

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

  // Start task with streaming
  const handleStart = useCallback(() => {
    if (taskInput.urls.length === 0 && !taskInput.instruction) return;
    
    setStats(prev => ({ ...prev, episodes: prev.episodes + 1, steps: 0, totalReward: 0, avgReward: 0 }));
    setIsRunning(true);
    setCurrentView('dashboard');
    setSessionId(null);
    setProgress({ urlIndex: 0, totalUrls: taskInput.urls.length, currentUrl: '' });
    setScrapeResult(null);
    setExtractedData({});
    setCurrentStep(null);
    setAllSteps([]);
    setExpandedStepIndex(null);
    
    // Build scrape request
    const scrapeRequest: ScrapeRequest = {
      assets: taskInput.urls,
      instructions: taskInput.instruction,
      output_instructions: taskInput.outputInstruction || 'Return as JSON',
      output_format: detectOutputFormat(taskInput.outputInstruction),
      complexity: taskInput.taskType,
      model: taskInput.selectedModel.split('/')[1] || 'llama-3.3-70b',
      provider: taskInput.selectedModel.split('/')[0] || 'nvidia',
      enable_memory: true,
      enable_plugins: taskInput.enabledPlugins,
      selected_agents: taskInput.selectedAgents,
      max_steps: 50,
    };
    
    // Add initial log
    setLogs(prev => [...prev, {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `Starting scrape with ${taskInput.urls.length} URLs`,
      source: 'system',
    }]);
    
    // Start streaming scrape
    abortControllerRef.current = apiClient.streamScrape(
      scrapeRequest,
      // onInit
      (sid) => {
        setSessionId(sid);
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          timestamp: new Date().toISOString(),
          level: 'info',
          message: `Session started: ${sid.slice(0, 8)}...`,
          source: 'scraper',
        }]);
      },
      // onUrlStart
      (url, index, total) => {
        setProgress({ urlIndex: index, totalUrls: total, currentUrl: url });
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          timestamp: new Date().toISOString(),
          level: 'info',
          message: `Processing URL ${index + 1}/${total}: ${url}`,
          source: 'scraper',
        }]);
      },
      // onStep
      (step) => {
        setCurrentStep(step);
        setAllSteps(prev => [...prev, step]);
        setStats(prev => {
          const steps = prev.steps + 1;
          const totalReward = prev.totalReward + step.reward;
          return {
            ...prev,
            steps,
            totalReward,
            avgReward: totalReward / steps,
          };
        });
        
        // Update extracted data
        if (step.extracted_data) {
          setExtractedData(prev => ({ ...prev, ...step.extracted_data }));
        }
        
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          timestamp: new Date().toISOString(),
          level: step.status === 'failed' ? 'error' : 'info',
          message: `[${step.action}] ${step.message} (reward: ${step.reward.toFixed(2)})`,
          source: step.url?.slice(0, 30) || 'step',
        }]);
      },
      // onUrlComplete
      (url, _index) => {
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          timestamp: new Date().toISOString(),
          level: 'info',
          message: `Completed: ${url}`,
          source: 'scraper',
        }]);
      },
      // onComplete
      (response) => {
        setScrapeResult(response);
        setIsRunning(false);
        setStats(prev => ({
          ...prev,
          totalReward: response.total_reward,
          avgReward: response.total_reward / Math.max(prev.steps, 1),
        }));

        const extractedAssets = Object.entries(response.extracted_data).map(([url, data]) => ({
          id: `${Date.now()}-${url}`,
          type: 'data' as const,
          name: `Data from ${url}`,
          source: 'ai' as const,
          content: JSON.stringify(data),
          timestamp: new Date().toISOString(),
        }));
        setAssets(prev => [...prev, ...extractedAssets]);
        
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          timestamp: new Date().toISOString(),
          level: response.errors.length > 0 ? 'warn' : 'info',
          message: `Scrape complete! Processed ${response.urls_processed} URLs, total reward: ${response.total_reward.toFixed(2)}`,
          source: 'system',
        }]);
      },
      // onError
      (error, url) => {
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          timestamp: new Date().toISOString(),
          level: 'error',
          message: `Error${url ? ` (${url})` : ''}: ${error}`,
          source: 'scraper',
        }]);
      }
    );
  }, [taskInput]);

  // Stop task
  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsRunning(false);
    setLogs(prev => [...prev, {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      level: 'warn',
      message: 'Scraping stopped by user',
      source: 'system',
    }]);
  }, []);
  
  // Copy result to clipboard
  const handleCopyResult = useCallback(() => {
    if (scrapeResult?.output) {
      navigator.clipboard.writeText(scrapeResult.output);
      setLogs(prev => [...prev, {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        level: 'info',
        message: 'Result copied to clipboard',
        source: 'system',
      }]);
    }
  }, [scrapeResult]);
  
  // Download result
  const handleDownloadResult = useCallback(() => {
    if (scrapeResult?.output) {
      const fileType =
        scrapeResult.output_format === 'csv'
          ? 'text/csv'
          : scrapeResult.output_format === 'markdown'
            ? 'text/markdown'
            : 'application/json';
      const extension =
        scrapeResult.output_format === 'csv'
          ? 'csv'
          : scrapeResult.output_format === 'markdown'
            ? 'md'
            : scrapeResult.output_format === 'text'
              ? 'txt'
              : 'json';
      const blob = new Blob([scrapeResult.output], { type: fileType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `scrape-result-${sessionId?.slice(0, 8) || 'unknown'}.${extension}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }, [scrapeResult, sessionId]);

  // Format time
  const formatTime = (isoString: string) => {
    return new Date(isoString).toLocaleTimeString('en-US', { hour12: false });
  };

  const safeHostname = (url: string) => {
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
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
      <div className="h-screen flex flex-col bg-slate-900">
        {/* System Status Banner */}
        {!isSystemOnline && (
          <div className="flex-shrink-0 px-4 py-2 bg-red-500/20 border-b border-red-500/30 flex items-center justify-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm text-red-400">System is offline. Please check your connection.</span>
          </div>
        )}
        
        {/* Main Content - Full Screen Navy Blue Theme */}
        <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-cyan-900/30">
          <div className="w-full max-w-4xl space-y-8">
            {/* Header */}
            <div className="text-center mb-12">
              <div className="flex items-center justify-center gap-3 mb-4">
                <div className="p-3 bg-cyan-500/20 rounded-xl border border-cyan-500/30">
                  <Zap className="w-8 h-8 text-cyan-400" />
                </div>
              </div>
              <h1 className="text-4xl font-bold text-white mb-3 tracking-tight">ScrapeRL</h1>
              <p className="text-lg text-cyan-300/70">AI-Powered Intelligent Web Scraping</p>
            </div>

            {/* Assets Section */}
            <div className="bg-slate-800/60 backdrop-blur-sm border border-cyan-500/20 rounded-2xl p-6 shadow-xl shadow-cyan-500/5">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-cyan-500/20 rounded-lg">
                  <Link className="w-5 h-5 text-cyan-400" />
                </div>
                <span className="text-lg font-semibold text-white">Assets</span>
                <Badge variant="info" size="sm">{taskInput.urls.length} URLs</Badge>
              </div>
              
              {/* URL Input */}
              <div className="flex gap-3 mb-4">
                <input
                  type="text"
                  placeholder="Enter URL (e.g., https://example.com)"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddUrl()}
                  className="flex-1 px-4 py-3 bg-slate-900/70 border border-cyan-500/30 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
                />
                <button
                  onClick={handleAddUrl}
                  disabled={!newUrl.trim()}
                  className="px-5 py-3 bg-cyan-500/20 hover:bg-cyan-500/30 disabled:bg-slate-700/50 border border-cyan-500/30 disabled:border-slate-600 text-cyan-400 disabled:text-slate-500 rounded-xl font-medium transition-all flex items-center gap-2"
                >
                  <Plus className="w-5 h-5" />
                  Add
                </button>
              </div>
              
              {/* URL List */}
              {taskInput.urls.length > 0 && (
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto p-2 bg-slate-900/50 rounded-xl border border-slate-700/50">
                  {taskInput.urls.map((url, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 px-3 py-2 bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 rounded-lg text-sm group hover:bg-cyan-500/20 transition-colors"
                    >
                      <Globe className="w-4 h-4 text-cyan-400" />
                      <span className="max-w-[200px] truncate">{url}</span>
                      <button
                        onClick={() => handleRemoveUrl(url)}
                        className="p-1 opacity-50 group-hover:opacity-100 hover:text-red-400 transition-all"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Instructions Section */}
            <div className="bg-slate-800/60 backdrop-blur-sm border border-cyan-500/20 rounded-2xl p-6 shadow-xl shadow-cyan-500/5">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                  <MessageSquare className="w-5 h-5 text-purple-400" />
                </div>
                <span className="text-lg font-semibold text-white">Instructions</span>
              </div>
              <textarea
                placeholder="What should I extract? (e.g., Extract all product names, prices, and descriptions from the page)"
                value={taskInput.instruction}
                onChange={(e) => setTaskInput(p => ({ ...p, instruction: e.target.value }))}
                rows={3}
                className="w-full px-4 py-3 bg-slate-900/70 border border-purple-500/30 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 resize-none transition-all"
              />
            </div>

            {/* Output Instructions */}
            <div className="bg-slate-800/60 backdrop-blur-sm border border-cyan-500/20 rounded-2xl p-6 shadow-xl shadow-cyan-500/5">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-emerald-500/20 rounded-lg">
                  <FileText className="w-5 h-5 text-emerald-400" />
                </div>
                <span className="text-lg font-semibold text-white">Output Format</span>
              </div>
              <textarea
                placeholder="How should the output be formatted? (e.g., JSON with fields: name, price, description, url)"
                value={taskInput.outputInstruction}
                onChange={(e) => setTaskInput(p => ({ ...p, outputInstruction: e.target.value }))}
                rows={2}
                className="w-full px-4 py-3 bg-slate-900/70 border border-emerald-500/30 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 resize-none transition-all"
              />
            </div>

            {/* Configuration Options */}
            <div className="flex flex-wrap items-center justify-center gap-4">
              {/* Model */}
              <button
                onClick={() => setShowModelPopup(true)}
                className="px-5 py-3 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 rounded-xl text-sm font-medium transition-all flex items-center gap-2 shadow-lg shadow-cyan-500/5"
              >
                <Cpu className="w-4 h-4" />
                {taskInput.selectedModel ? taskInput.selectedModel.split('/')[1] : 'Select Model'}
              </button>
              
              {/* Vision */}
              <button
                onClick={() => setShowVisionPopup(true)}
                className={classNames(
                  'px-5 py-3 border rounded-xl text-sm font-medium transition-all flex items-center gap-2 shadow-lg',
                  taskInput.selectedVisionModel 
                    ? 'bg-pink-500/10 border-pink-500/30 text-pink-400 shadow-pink-500/5' 
                    : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:border-pink-500/30 hover:text-pink-400'
                )}
              >
                <Eye className="w-4 h-4" />
                {taskInput.selectedVisionModel ? 'Vision ✓' : 'Vision'}
              </button>
              
              {/* Agents */}
              <button
                onClick={() => setShowAgentPopup(true)}
                className="px-5 py-3 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-xl text-sm font-medium transition-all flex items-center gap-2 shadow-lg shadow-purple-500/5"
              >
                <Bot className="w-4 h-4" />
                Agents {taskInput.selectedAgents.length > 0 && `(${taskInput.selectedAgents.length})`}
              </button>
              
              {/* Plugins */}
              <button
                onClick={() => setShowPluginPopup(true)}
                className="px-5 py-3 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-xl text-sm font-medium transition-all flex items-center gap-2 shadow-lg shadow-amber-500/5"
              >
                <Plug className="w-4 h-4" />
                Plugins {taskInput.enabledPlugins.length > 0 && `(${taskInput.enabledPlugins.length})`}
              </button>
              
              {/* Task Type */}
              <button
                onClick={() => setShowTaskTypePopup(true)}
                className={classNames(
                  'px-5 py-3 border rounded-xl text-sm font-medium transition-all flex items-center gap-2 shadow-lg',
                  taskInput.taskType === 'low' && 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-emerald-500/5',
                  taskInput.taskType === 'medium' && 'bg-amber-500/10 border-amber-500/30 text-amber-400 shadow-amber-500/5',
                  taskInput.taskType === 'high' && 'bg-red-500/10 border-red-500/30 text-red-400 shadow-red-500/5'
                )}
              >
                <Target className="w-4 h-4" />
                {taskTypes.find(t => t.id === taskInput.taskType)?.icon} {taskInput.taskType.charAt(0).toUpperCase() + taskInput.taskType.slice(1)}
              </button>
            </div>

            {/* Start Button */}
            <div className="flex justify-center pt-6">
              <button
                onClick={handleStart}
                disabled={taskInput.urls.length === 0 || !isSystemOnline}
                className="px-10 py-4 bg-gradient-to-r from-cyan-500 to-cyan-600 hover:from-cyan-400 hover:to-cyan-500 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed text-white rounded-2xl font-semibold text-lg transition-all flex items-center gap-3 shadow-xl shadow-cyan-500/30 disabled:shadow-none transform hover:scale-[1.02] disabled:hover:scale-100"
              >
                <Play className="w-6 h-6" />
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
                        {asset.type === 'image' && <ImageIcon className="w-4 h-4 text-pink-400 flex-shrink-0" />}
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
    <div className="h-screen flex flex-col bg-slate-900">
      {/* Main 3-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Active Components */}
        <div className="w-56 flex-shrink-0 bg-slate-800/50 border-r border-cyan-500/10 overflow-y-auto p-3 space-y-3">
          {/* Back to Input */}
          <button
            onClick={() => { setCurrentView('input'); handleStop(); }}
            className="w-full flex items-center gap-2 px-3 py-2 bg-slate-700/50 hover:bg-slate-700 border border-slate-600/50 rounded-xl text-sm text-slate-300 transition-all"
          >
            <ChevronRight className="w-4 h-4 rotate-180" />
            New Task
          </button>

          {/* Progress Bar */}
          {isRunning && progress.totalUrls > 0 && (
            <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-cyan-400 font-medium">Progress</span>
                <span className="text-xs text-cyan-300">{progress.urlIndex + 1}/{progress.totalUrls}</span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-500"
                  style={{ width: `${((progress.urlIndex + 1) / progress.totalUrls) * 100}%` }}
                />
              </div>
              <p className="text-[10px] text-slate-400 mt-2 truncate">{progress.currentUrl}</p>
            </div>
          )}

          {/* Agents */}
          <Accordion title="Agents" icon={Bot} badge={taskInput.selectedAgents.length} color="text-purple-400" defaultOpen>
            {taskInput.selectedAgents.length === 0 ? (
              <p className="text-xs text-slate-500 p-2">No agents selected</p>
            ) : (
              taskInput.selectedAgents.map((agentId) => {
                const agent = agents.find(a => a.type === agentId);
                return (
                  <div key={agentId} className="flex items-center justify-between p-2 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`}></div>
                      <span className="text-xs text-white">{agent?.name || agentId}</span>
                    </div>
                    <button onClick={() => showInfo(agent?.name || agentId, agent?.description || '', { Type: agentId })} className="text-slate-500 hover:text-slate-300">
                      <Info className="w-3 h-3" />
                    </button>
                  </div>
                );
              })
            )}
          </Accordion>

          {/* Plugins */}
          <Accordion title="Plugins" icon={Plug} badge={taskInput.enabledPlugins.length} color="text-amber-400">
            {taskInput.enabledPlugins.length === 0 ? (
              <p className="text-xs text-slate-500 p-2">No plugins enabled</p>
            ) : (
              taskInput.enabledPlugins.map((pluginId) => (
                <div key={pluginId} className="p-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                  <span className="text-xs text-white">{pluginId}</span>
                </div>
              ))
            )}
          </Accordion>

          {/* System Status */}
          <div className="p-3 bg-slate-900/50 border border-slate-700/50 rounded-xl">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-400">Status</span>
              <Badge variant={isSystemOnline ? 'success' : 'error'} size="sm">
                {isRunning ? 'Running' : isSystemOnline ? 'Online' : 'Offline'}
              </Badge>
            </div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-400">Model</span>
              <span className="text-xs text-cyan-300">{taskInput.selectedModel.split('/')[1]}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Complexity</span>
              <span className={classNames(
                'text-xs',
                taskInput.taskType === 'low' ? 'text-emerald-400' :
                taskInput.taskType === 'medium' ? 'text-amber-400' : 'text-red-400'
              )}>{taskInput.taskType.toUpperCase()}</span>
            </div>
          </div>
        </div>

        {/* Center Content */}
        <div className="flex-1 flex flex-col overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800/50 to-cyan-900/10">
          {/* Stats Header - Session-based, start at 0 */}
          <div className="flex-shrink-0 p-4 bg-slate-800/30 border-b border-cyan-500/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-8">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-cyan-500/20 rounded-lg">
                    <Layers className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-white">{stats.episodes}</p>
                    <p className="text-xs text-slate-500">Episodes</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-500/20 rounded-lg">
                    <Target className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-white">{stats.steps}</p>
                    <p className="text-xs text-slate-500">Steps</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-500/20 rounded-lg">
                    <TrendingUp className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-white">{stats.totalReward.toFixed(2)}</p>
                    <p className="text-xs text-slate-500">Total Reward</p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4">
                {/* Control Buttons */}
                {isRunning ? (
                  <button
                    onClick={handleStop}
                    className="px-6 py-2.5 bg-red-500 hover:bg-red-600 text-white rounded-xl font-medium transition-all flex items-center gap-2 shadow-lg shadow-red-500/20"
                  >
                    <Pause className="w-4 h-4" />
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={handleStart}
                    disabled={taskInput.urls.length === 0}
                    className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-cyan-600 hover:from-cyan-400 hover:to-cyan-500 disabled:from-slate-600 disabled:to-slate-700 text-white rounded-xl font-medium transition-all flex items-center gap-2 shadow-lg shadow-cyan-500/20"
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
            <div className="h-full bg-slate-900/50 border border-cyan-500/10 rounded-2xl p-4">
              {isRunning ? (
                <div className="h-full flex flex-col">
                  {/* Steps Accordion */}
                  <div className="flex-shrink-0 mb-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Layers className="w-5 h-5 text-cyan-400 animate-pulse" />
                        <span className="text-sm font-semibold text-white">Execution Steps</span>
                        <Badge variant="info" size="sm">{allSteps.length}</Badge>
                      </div>
                      {currentStep && (
                        <Badge 
                          variant={currentStep.status === 'completed' ? 'success' : currentStep.status === 'failed' ? 'error' : 'info'}
                        >
                          {currentStep.action.toUpperCase()}
                        </Badge>
                      )}
                    </div>
                    
                    {/* Step Accordion List */}
                    <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
                      {allSteps.length === 0 ? (
                        <div className="p-4 bg-slate-800/50 rounded-xl text-center">
                          <div className="animate-spin w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto mb-2"></div>
                          <p className="text-sm text-slate-400">Initializing scraper...</p>
                        </div>
                      ) : (
                        allSteps.map((step, index) => (
                          <StepAccordionItem
                            key={`${step.step_number}-${index}`}
                            step={step}
                            isExpanded={expandedStepIndex === index}
                            onToggle={() => setExpandedStepIndex(expandedStepIndex === index ? null : index)}
                            isLatest={index === allSteps.length - 1}
                          />
                        ))
                      )}
                    </div>
                  </div>

                  {/* Extracted Data Preview */}
                  <div className="flex-1 overflow-auto">
                    <div className="flex items-center gap-2 mb-3">
                      <Database className="w-5 h-5 text-emerald-400" />
                      <span className="text-sm font-semibold text-white">Live Extracted Data</span>
                    </div>
                    <div className="p-4 bg-slate-800/50 rounded-xl min-h-[150px] max-h-[250px] overflow-auto">
                      <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap">
                        {Object.keys(extractedData).length > 0 
                          ? JSON.stringify(extractedData, null, 2)
                          : '{\n  "status": "extracting...",\n  "data": []\n}'
                        }
                      </pre>
                    </div>
                  </div>
                </div>
              ) : scrapeResult ? (
                <div className="h-full flex flex-col">
                  {/* Result Header */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${scrapeResult.status === 'completed' ? 'bg-emerald-500/20' : 'bg-amber-500/20'}`}>
                        {scrapeResult.status === 'completed' ? (
                          <CheckCircle className="w-6 h-6 text-emerald-400" />
                        ) : (
                          <AlertCircle className="w-6 h-6 text-amber-400" />
                        )}
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-white">Scraping Complete</h3>
                        <p className="text-sm text-slate-400">
                          {scrapeResult.urls_processed} URLs • {scrapeResult.total_steps} steps • {scrapeResult.duration_seconds.toFixed(1)}s • Reward: {scrapeResult.total_reward.toFixed(2)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCopyResult}
                        className="px-4 py-2 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 text-cyan-400 rounded-lg text-sm font-medium transition-all flex items-center gap-2"
                      >
                        <Copy className="w-4 h-4" />
                        Copy
                      </button>
                      <button
                        onClick={handleDownloadResult}
                        className="px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 text-emerald-400 rounded-lg text-sm font-medium transition-all flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </button>
                    </div>
                  </div>

                  {/* Steps Summary (collapsed) */}
                  {allSteps.length > 0 && (
                    <div className="mb-4">
                      <Accordion title={`Execution Steps (${allSteps.length})`} icon={Layers} color="text-cyan-400">
                        <div className="space-y-1 max-h-[200px] overflow-y-auto">
                          {allSteps.map((step, index) => (
                            <div 
                              key={`result-${step.step_number}-${index}`}
                              className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg text-xs"
                            >
                              <div className="flex items-center gap-2">
                                {React.createElement(getStepIcon(step.action), { 
                                  className: classNames('w-3 h-3', getStepColor(step.action, step.status).split(' ')[0]) 
                                })}
                                <span className="text-slate-300">{step.action}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-emerald-400">+{step.reward.toFixed(2)}</span>
                                {step.status === 'completed' ? (
                                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                                ) : step.status === 'failed' ? (
                                  <XCircle className="w-3 h-3 text-red-400" />
                                ) : (
                                  <Clock className="w-3 h-3 text-cyan-400" />
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </Accordion>
                    </div>
                  )}

                  {/* Result Content - Full Output */}
                  <div className="flex-1 overflow-auto">
                    <div className="flex items-center gap-2 mb-2">
                      <FileJson className="w-4 h-4 text-amber-400" />
                      <span className="text-sm font-medium text-white">Output ({scrapeResult.output_format})</span>
                    </div>
                    <div className="p-4 bg-slate-800/50 rounded-xl overflow-auto max-h-[400px]">
                      <pre className="text-sm text-slate-300 font-mono whitespace-pre-wrap">
                        {scrapeResult.output}
                      </pre>
                    </div>
                  </div>

                  {/* Errors */}
                  {scrapeResult.errors.length > 0 && (
                    <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
                      <h4 className="text-sm font-medium text-red-400 mb-2">Errors ({scrapeResult.errors.length})</h4>
                      {scrapeResult.errors.map((err, idx) => (
                        <p key={idx} className="text-xs text-red-300">{err}</p>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center">
                  <div className="w-20 h-20 bg-cyan-500/10 rounded-2xl flex items-center justify-center mb-6 border border-cyan-500/20">
                    <Globe className="w-10 h-10 text-cyan-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-2">Ready to Scrape</h3>
                  <p className="text-sm text-slate-400 max-w-md mb-4">
                    {taskInput.urls.length} URLs loaded. Click Start to begin scraping.
                  </p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {taskInput.urls.slice(0, 3).map((url, idx) => (
                      <Badge key={idx} variant="info" size="sm">{safeHostname(url)}</Badge>
                    ))}
                    {taskInput.urls.length > 3 && (
                      <Badge variant="neutral" size="sm">+{taskInput.urls.length - 3} more</Badge>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Logs Terminal */}
          <div className="flex-shrink-0 h-36 bg-slate-900 border-t border-cyan-500/10">
            <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-medium text-slate-300">Live Logs</span>
                {isRunning && <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>}
              </div>
              <button onClick={() => setLogs([])} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
                Clear
              </button>
            </div>
            <div className="h-[calc(100%-32px)] overflow-y-auto p-3 font-mono text-xs">
              {logs.length === 0 ? (
                <p className="text-slate-600">Waiting for logs...</p>
              ) : (
                logs.slice(-50).map((log) => (
                  <div key={log.id} className="flex items-start gap-2 py-0.5">
                    <span className="text-slate-600">[{formatTime(log.timestamp)}]</span>
                    <span className={getLogLevelColor(log.level)}>[{log.level.toUpperCase()}]</span>
                    {log.source && <span className="text-purple-400">[{log.source}]</span>}
                    <span className="text-slate-300">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="w-72 flex-shrink-0 bg-slate-800/50 border-l border-cyan-500/10 overflow-y-auto p-4 space-y-4">
          {/* Input Summary */}
          <div className="bg-slate-900/50 border border-slate-700/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-cyan-400" />
                <span className="text-sm font-semibold text-white">Task Input</span>
              </div>
              <button
                onClick={() => setCurrentView('input')}
                className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                Edit
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-slate-500 text-xs mb-1">URLs ({taskInput.urls.length})</p>
                <p className="text-slate-300 truncate">{taskInput.urls[0] || 'None'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Instruction</p>
                <p className="text-slate-300 line-clamp-2">{taskInput.instruction || 'None'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Output Format</p>
                <p className="text-slate-300 truncate">{taskInput.outputInstruction || 'JSON'}</p>
              </div>
            </div>
          </div>

          {/* Memories */}
          <div className="bg-slate-900/50 border border-slate-700/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-purple-400" />
                <span className="text-sm font-semibold text-white">Memory</span>
              </div>
              <button onClick={() => setShowMemoriesPopup(true)} className="text-xs text-purple-400 hover:text-purple-300">
                Manage
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-3 bg-slate-800/50 rounded-lg text-center">
                <p className="text-lg font-bold text-emerald-400">{memoryData?.short_term_count || 0}</p>
                <p className="text-[10px] text-slate-500">Short-term</p>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg text-center">
                <p className="text-lg font-bold text-cyan-400">{memoryData?.working_count || 0}</p>
                <p className="text-[10px] text-slate-500">Working</p>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg text-center">
                <p className="text-lg font-bold text-purple-400">{memoryData?.long_term_count || 0}</p>
                <p className="text-[10px] text-slate-500">Long-term</p>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg text-center">
                <p className="text-lg font-bold text-amber-400">{memories.length}</p>
                <p className="text-[10px] text-slate-500">Session</p>
              </div>
            </div>
          </div>

          {/* Assets */}
          <div className="bg-slate-900/50 border border-slate-700/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-amber-400" />
                <span className="text-sm font-semibold text-white">Assets</span>
              </div>
              <Badge variant="neutral" size="sm">{assets.length}</Badge>
            </div>
            
            {assets.length === 0 ? (
              <p className="text-center py-4 text-slate-500 text-xs">No assets yet</p>
            ) : (
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {assets.slice(0, 5).map((asset) => (
                  <div key={asset.id} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      {asset.type === 'url' && <Link className="w-3 h-3 text-cyan-400 flex-shrink-0" />}
                      {asset.type === 'data' && <Database className="w-3 h-3 text-emerald-400 flex-shrink-0" />}
                      <span className="text-slate-300 truncate">{asset.name.slice(0, 25)}</span>
                    </div>
                    <Badge variant={asset.source === 'ai' ? 'info' : 'neutral'} size="sm">{asset.source}</Badge>
                  </div>
                ))}
              </div>
            )}
            
            <button
              onClick={() => setShowAssetsPopup(true)}
              className="w-full mt-3 px-3 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-lg text-xs font-medium transition-all"
            >
              View All Assets
            </button>
          </div>
        </div>
      </div>

      {/* Popups */}
      {renderPopups()}
    </div>
  );
};

export default Dashboard;
