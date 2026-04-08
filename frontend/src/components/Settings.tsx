import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings as SettingsIcon,
  Key,
  AlertCircle,
  CheckCircle,
  Eye,
  EyeOff,
  Zap,
  Server,
  Palette,
  Bell,
  Shield,
  Cpu,
  Globe,
  Wallet,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select, Toggle } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { apiClient } from '@/api/client';
import type { SystemSettings } from '@/types';
import { classNames } from '@/utils/helpers';

interface SettingsProps {
  className?: string;
}

interface ApiKeyState {
  openai: string;
  anthropic: string;
  google: string;
  groq: string;
}

interface ModelOption {
  provider: string;
  model: string;
  name: string;
  description: string;
  default?: boolean;
}

interface SettingsData {
  api_keys_configured: Record<string, boolean>;
  selected_model: { provider: string; model: string };
  available_models: ModelOption[];
  plugins_installed: string[];
}

type SettingsSection = 'general' | 'api-keys' | 'models' | 'budget' | 'appearance' | 'notifications' | 'advanced';

const sectionConfig: { id: SettingsSection; label: string; icon: React.ElementType; description: string }[] = [
  { id: 'general', label: 'General', icon: SettingsIcon, description: 'Basic application settings' },
  { id: 'api-keys', label: 'API Keys', icon: Key, description: 'Configure provider API keys' },
  { id: 'models', label: 'Models', icon: Cpu, description: 'AI model selection' },
  { id: 'budget', label: 'Budget & Limits', icon: Wallet, description: 'API usage limits' },
  { id: 'appearance', label: 'Appearance', icon: Palette, description: 'UI customization' },
  { id: 'notifications', label: 'Notifications', icon: Bell, description: 'Alert preferences' },
  { id: 'advanced', label: 'Advanced', icon: Shield, description: 'Advanced settings' },
];

export const Settings: React.FC<SettingsProps> = ({ className }) => {
  const queryClient = useQueryClient();
  const [activeSection, setActiveSection] = useState<SettingsSection>('general');
  const [localSettings, setLocalSettings] = useState<Partial<SystemSettings>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [budgetEnabled, setBudgetEnabled] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKeyState>({
    openai: '',
    anthropic: '',
    google: '',
    groq: '',
  });

  // Fetch settings from new API
  const { data: settingsData, isLoading: settingsLoading } = useQuery<SettingsData>({
    queryKey: ['client-settings'],
    queryFn: async () => {
      const res = await fetch('/api/settings/');
      return res.json();
    },
  });

  // Fetch API key requirement status
  const { data: keyRequired } = useQuery({
    queryKey: ['api-key-required'],
    queryFn: async () => {
      const res = await fetch('/api/settings/api-key/required');
      return res.json();
    },
    refetchInterval: 5000,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.healthCheck(),
    refetchInterval: 10000,
  });

  const normalizedHealthStatus = typeof health?.status === 'string'
    ? health.status.toLowerCase()
    : '';
  const isBackendOnline =
    normalizedHealthStatus === 'healthy'
    || normalizedHealthStatus === 'ok'
    || normalizedHealthStatus === 'ready';

  // Mutation to update API key
  const updateApiKeyMutation = useMutation({
    mutationFn: async ({ provider, api_key }: { provider: string; api_key: string }) => {
      const res = await fetch('/api/settings/api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['client-settings'] });
      queryClient.invalidateQueries({ queryKey: ['api-key-required'] });
    },
  });

  // Mutation to select model
  const selectModelMutation = useMutation({
    mutationFn: async ({ provider, model }: { provider: string; model: string }) => {
      const res = await fetch('/api/settings/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['client-settings'] });
      queryClient.invalidateQueries({ queryKey: ['api-key-required'] });
    },
  });

  const handleSaveApiKey = (provider: string) => {
    const key = apiKeys[provider as keyof ApiKeyState];
    if (key) {
      updateApiKeyMutation.mutate({ provider, api_key: key });
    }
  };

  const handleModelChange = (value: string) => {
    const [provider, model] = value.split('/');
    selectModelMutation.mutate({ provider, model });
  };

  const toggleShowKey = (provider: string) => {
    setShowKeys((prev) => ({ ...prev, [provider]: !prev[provider] }));
  };

  const providers = [
    { id: 'groq', name: 'Groq', icon: '⚡', description: 'Fast inference (Recommended)' },
    { id: 'google', name: 'Google', icon: '🔮', description: 'Gemini models' },
    { id: 'openai', name: 'OpenAI', icon: '🤖', description: 'GPT-4 models' },
    { id: 'anthropic', name: 'Anthropic', icon: '🧠', description: 'Claude models' },
  ];

  const modelOptions = (settingsData?.available_models ?? []).map((m) => ({
    value: `${m.provider}/${m.model}`,
    label: `${m.name}${m.default ? ' (Default)' : ''}`,
  }));

  const currentModel = settingsData?.selected_model
    ? `${settingsData.selected_model.provider}/${settingsData.selected_model.model}`
    : 'groq/gpt-oss-120b';

  const renderSectionContent = () => {
    switch (activeSection) {
      case 'general':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">General Settings</h3>
              <p className="text-sm text-gray-400">Configure basic application behavior</p>
            </div>

            {/* API Key Required Warning */}
            {keyRequired?.required && (
              <div className="flex items-center gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-amber-400">API Key Required</p>
                  <p className="text-xs text-amber-400/70">{keyRequired.message}</p>
                </div>
              </div>
            )}

            <div className="space-y-4">
              <Toggle
                label="WebSocket Updates"
                description="Enable real-time episode updates via WebSocket connection"
                checked={localSettings.enableWebSocket ?? true}
                onChange={(checked) => setLocalSettings((prev) => ({ ...prev, enableWebSocket: checked }))}
              />
              <Toggle
                label="Memory Persistence"
                description="Persist memory data across episodes for better context retention"
                checked={localSettings.memoryPersistence ?? false}
                onChange={(checked) => setLocalSettings((prev) => ({ ...prev, memoryPersistence: checked }))}
              />
              <Toggle
                label="Auto-save Episodes"
                description="Automatically save episode data when completed"
                checked={localSettings.autoSave ?? true}
                onChange={(checked) => setLocalSettings((prev) => ({ ...prev, autoSave: checked }))}
              />
              <Toggle
                label="Debug Mode"
                description="Enable verbose logging and debugging information"
                checked={localSettings.debugMode ?? false}
                onChange={(checked) => setLocalSettings((prev) => ({ ...prev, debugMode: checked }))}
              />
            </div>

            {/* System Status */}
            <div className="pt-4 border-t border-gray-700/50">
              <h4 className="text-sm font-medium text-gray-300 mb-3">System Status</h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Server className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs text-gray-400">Backend</span>
                  </div>
                  <p className="text-sm font-medium text-white mt-1">
                    {isBackendOnline ? 'Connected' : 'Disconnected'}
                  </p>
                </div>
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-cyan-400" />
                    <span className="text-xs text-gray-400">Version</span>
                  </div>
                  <p className="text-sm font-medium text-white mt-1">{health?.version || 'v0.1.0'}</p>
                </div>
              </div>
            </div>
          </div>
        );

      case 'api-keys':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">API Keys</h3>
              <p className="text-sm text-gray-400">
                Configure your provider API keys. Server keys are used by default, but you can override them here.
              </p>
            </div>

            <div className="space-y-4">
              {providers.map((provider) => {
                const isConfigured = settingsData?.api_keys_configured?.[provider.id] ?? false;
                return (
                  <div key={provider.id} className="p-4 bg-gray-900/50 border border-gray-700/30 rounded-xl">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{provider.icon}</span>
                        <div>
                          <span className="text-sm font-medium text-white">{provider.name}</span>
                          <p className="text-xs text-gray-500">{provider.description}</p>
                        </div>
                      </div>
                      <Badge variant={isConfigured ? 'success' : 'warning'} size="sm">
                        {isConfigured ? 'Active' : 'Not Set'}
                      </Badge>
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1 relative">
                        <Input
                          type={showKeys[provider.id] ? 'text' : 'password'}
                          placeholder={`Enter ${provider.name} API key...`}
                          value={apiKeys[provider.id as keyof ApiKeyState]}
                          onChange={(e) =>
                            setApiKeys((prev) => ({
                              ...prev,
                              [provider.id]: e.target.value,
                            }))
                          }
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShowKey(provider.id)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                        >
                          {showKeys[provider.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => handleSaveApiKey(provider.id)}
                        disabled={!apiKeys[provider.id as keyof ApiKeyState]}
                      >
                        Save
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>

            {updateApiKeyMutation.isSuccess && (
              <div className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-emerald-400">API key saved successfully</span>
              </div>
            )}
          </div>
        );

      case 'models':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">AI Models</h3>
              <p className="text-sm text-gray-400">Select the AI model to use for scraping tasks</p>
            </div>

            <div className="p-4 bg-gray-900/50 border border-gray-700/30 rounded-xl">
              <div className="flex items-center gap-2 text-sm font-medium text-white mb-3">
                <Zap className="w-4 h-4 text-emerald-400" />
                Active Model
              </div>
              <Select
                label=""
                options={modelOptions}
                value={currentModel}
                onChange={(e) => handleModelChange(e.target.value)}
                placeholder="Select model"
              />
              {selectModelMutation.isPending && (
                <p className="text-xs text-gray-400 mt-2">Switching model...</p>
              )}
            </div>

            {/* Model Categories */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-xl">
                <h4 className="text-sm font-medium text-cyan-400 mb-2">Text Models</h4>
                <p className="text-xs text-gray-400">GPT-4, Claude, Gemini for text generation</p>
              </div>
              <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-xl">
                <h4 className="text-sm font-medium text-purple-400 mb-2">Vision Models</h4>
                <p className="text-xs text-gray-400">GPT-4V, Gemini Pro Vision for image analysis</p>
              </div>
              <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                <h4 className="text-sm font-medium text-amber-400 mb-2">Embedding Models</h4>
                <p className="text-xs text-gray-400">Text embeddings for semantic search</p>
              </div>
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
                <h4 className="text-sm font-medium text-emerald-400 mb-2">Fast Models</h4>
                <p className="text-xs text-gray-400">Groq, Mistral for fast inference</p>
              </div>
            </div>
          </div>
        );

      case 'budget':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">Budget & Limits</h3>
              <p className="text-sm text-gray-400">Configure API usage limits and budget controls</p>
            </div>

            <div className="p-4 bg-gray-900/50 border border-gray-700/30 rounded-xl">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Wallet className="w-5 h-5 text-amber-400" />
                  <div>
                    <h4 className="text-sm font-medium text-white">Enable Budget Limits</h4>
                    <p className="text-xs text-gray-500">Control API spending with usage limits</p>
                  </div>
                </div>
                <button
                  onClick={() => setBudgetEnabled(!budgetEnabled)}
                  className={classNames(
                    'relative w-12 h-6 rounded-full transition-colors',
                    budgetEnabled ? 'bg-emerald-500' : 'bg-gray-600'
                  )}
                >
                  <span
                    className={classNames(
                      'absolute top-1 w-4 h-4 bg-white rounded-full transition-transform',
                      budgetEnabled ? 'translate-x-7' : 'translate-x-1'
                    )}
                  />
                </button>
              </div>

              {budgetEnabled ? (
                <div className="space-y-4 pt-4 border-t border-gray-700/50">
                  <div>
                    <label className="text-xs text-gray-400 mb-2 block">Daily Limit ($)</label>
                    <Input type="number" placeholder="10.00" className="bg-gray-800/50" />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 mb-2 block">Monthly Limit ($)</label>
                    <Input type="number" placeholder="100.00" className="bg-gray-800/50" />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 mb-2 block">Max Tokens per Request</label>
                    <Input type="number" placeholder="4096" className="bg-gray-800/50" />
                  </div>
                  <Toggle
                    label="Alert at 80% usage"
                    description="Receive notification when approaching limit"
                    checked={true}
                    onChange={() => {}}
                  />
                </div>
              ) : (
                <div className="pt-4 border-t border-gray-700/50">
                  <p className="text-sm text-gray-500 text-center py-4">
                    Budget limits are disabled. Enable to control API spending.
                  </p>
                </div>
              )}
            </div>
          </div>
        );

      case 'appearance':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">Appearance</h3>
              <p className="text-sm text-gray-400">Customize the look and feel of ScrapeRL</p>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-gray-900/50 border border-gray-700/30 rounded-xl">
                <h4 className="text-sm font-medium text-white mb-3">Theme</h4>
                <div className="grid grid-cols-3 gap-3">
                  <button className="p-3 bg-gray-800 border-2 border-emerald-500 rounded-lg text-center">
                    <div className="w-8 h-8 bg-gray-900 rounded mx-auto mb-2" />
                    <span className="text-xs text-white">Dark</span>
                  </button>
                  <button className="p-3 bg-gray-800 border border-gray-600 rounded-lg text-center opacity-50">
                    <div className="w-8 h-8 bg-white rounded mx-auto mb-2" />
                    <span className="text-xs text-gray-400">Light</span>
                  </button>
                  <button className="p-3 bg-gray-800 border border-gray-600 rounded-lg text-center opacity-50">
                    <div className="w-8 h-8 bg-gradient-to-b from-white to-gray-900 rounded mx-auto mb-2" />
                    <span className="text-xs text-gray-400">Auto</span>
                  </button>
                </div>
              </div>

              <Toggle
                label="Compact Mode"
                description="Reduce padding and spacing for more content"
                checked={false}
                onChange={() => {}}
              />
              <Toggle
                label="Show Animations"
                description="Enable UI animations and transitions"
                checked={true}
                onChange={() => {}}
              />
            </div>
          </div>
        );

      case 'notifications':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">Notifications</h3>
              <p className="text-sm text-gray-400">Configure when and how you receive alerts</p>
            </div>

            <div className="space-y-4">
              <Toggle
                label="Episode Completion"
                description="Notify when an episode finishes"
                checked={true}
                onChange={() => {}}
              />
              <Toggle
                label="Error Alerts"
                description="Alert on scraping errors"
                checked={true}
                onChange={() => {}}
              />
              <Toggle
                label="Budget Warnings"
                description="Warn when approaching budget limits"
                checked={true}
                onChange={() => {}}
              />
              <Toggle
                label="System Updates"
                description="Notify about new features and updates"
                checked={false}
                onChange={() => {}}
              />
            </div>
          </div>
        );

      case 'advanced':
        return (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">Advanced Settings</h3>
              <p className="text-sm text-gray-400">For power users and developers</p>
            </div>

            <div className="space-y-4">
              <Toggle
                label="Developer Mode"
                description="Enable advanced debugging tools"
                checked={false}
                onChange={() => {}}
              />
              <Toggle
                label="Experimental Features"
                description="Try new features before release"
                checked={false}
                onChange={() => {}}
              />
              <Toggle
                label="Verbose Logging"
                description="Log all API requests and responses"
                checked={false}
                onChange={() => {}}
              />

              <div className="pt-4 border-t border-gray-700/50">
                <h4 className="text-sm font-medium text-white mb-3">Data Management</h4>
                <div className="flex gap-3">
                  <Button variant="secondary" size="sm">
                    Export Data
                  </Button>
                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300">
                    Clear Cache
                  </Button>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className={classNames('flex h-[calc(100vh-120px)]', className)}>
      {/* Left Sidebar */}
      <div className="w-64 bg-gray-800/30 border-r border-gray-700/50 flex flex-col">
        <div className="p-4 border-b border-gray-700/50">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-purple-400" />
            Settings
          </h2>
          <p className="text-xs text-gray-500 mt-1">Configure your environment</p>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {sectionConfig.map((section) => {
            const Icon = section.icon;
            const isActive = activeSection === section.id;
            return (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={classNames(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all group',
                  isActive
                    ? 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400'
                    : 'hover:bg-gray-700/50 text-gray-400 hover:text-gray-200'
                )}
              >
                <Icon className={classNames('w-4 h-4', isActive ? 'text-emerald-400' : 'text-gray-500 group-hover:text-gray-300')} />
                <span className="text-sm font-medium">{section.label}</span>
                <ChevronRight className={classNames('w-4 h-4 ml-auto transition-transform', isActive ? 'rotate-90' : '')} />
              </button>
            );
          })}
        </nav>

        {/* Status Footer */}
        <div className="p-4 border-t border-gray-700/50">
          <div className="flex items-center gap-2">
            <div className={classNames('w-2 h-2 rounded-full', isBackendOnline ? 'bg-emerald-400' : 'bg-red-400')} />
            <span className="text-xs text-gray-400">{isBackendOnline ? 'System Online' : 'System Offline'}</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6">
          {settingsLoading ? (
            <div className="flex items-center justify-center py-16">
              <div className="flex flex-col items-center gap-3">
                <SettingsIcon className="w-8 h-8 text-gray-500 animate-spin" />
                <p className="text-gray-400">Loading settings...</p>
              </div>
            </div>
          ) : (
            renderSectionContent()
          )}
        </div>
      </div>
    </div>
  );
};

export default Settings;
