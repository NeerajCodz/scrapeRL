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
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select, Toggle } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { apiClient } from '@/api/client';
import type { SystemSettings } from '@/types';

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

export const Settings: React.FC<SettingsProps> = ({ className }) => {
  const queryClient = useQueryClient();
  const [localSettings, setLocalSettings] = useState<Partial<SystemSettings>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
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

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-lg">
              <SettingsIcon className="w-6 h-6 text-purple-400" />
            </div>
            Settings
          </h1>
          <p className="text-gray-400 mt-1">Configure your ScrapeRL environment</p>
        </div>
        {health && (
          <Badge variant={health.status === 'ok' ? 'success' : 'error'} dot>
            {health.status === 'ok' ? 'Connected' : 'Disconnected'}
          </Badge>
        )}
      </div>

      {settingsLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <SettingsIcon className="w-8 h-8 text-gray-500 animate-spin" />
            <p className="text-gray-400">Loading settings...</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-6">
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

            {/* Model Selection */}
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-white mb-4">
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
              <p className="text-xs text-gray-500 mt-3">
                Select the AI model to use for scraping tasks. Different models have different capabilities and costs.
              </p>
            </div>

            {/* Connection Settings */}
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-white mb-4">
                <Server className="w-4 h-4 text-cyan-400" />
                Connection Settings
              </div>
              <div className="space-y-4">
                <Toggle
                  label="WebSocket Updates"
                  description="Enable real-time episode updates"
                  checked={localSettings.enableWebSocket ?? true}
                  onChange={(checked) => {
                    setLocalSettings((prev) => ({ ...prev, enableWebSocket: checked }));
                  }}
                />
                <Toggle
                  label="Memory Persistence"
                  description="Persist memory across episodes"
                  checked={localSettings.memoryPersistence ?? false}
                  onChange={(checked) => {
                    setLocalSettings((prev) => ({ ...prev, memoryPersistence: checked }));
                  }}
                />
              </div>
            </div>
          </div>

          {/* Right Column - API Keys */}
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-white mb-2">
              <Key className="w-4 h-4 text-amber-400" />
              API Keys
            </div>
            <p className="text-xs text-gray-400 mb-5">
              Configure your API keys. Server keys are used by default, but you can override them here.
            </p>
            
            <div className="space-y-4">
              {providers.map((provider) => {
                const isConfigured = settingsData?.api_keys_configured?.[provider.id] ?? false;
                return (
                  <div key={provider.id} className="p-4 bg-gray-900/50 border border-gray-700/30 rounded-xl">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{provider.icon}</span>
                        <div>
                          <span className="text-sm font-medium text-white">
                            {provider.name}
                          </span>
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
                          {showKeys[provider.id] ? (
                            <EyeOff className="w-4 h-4" />
                          ) : (
                            <Eye className="w-4 h-4" />
                          )}
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

            {/* Status Messages */}
            {updateApiKeyMutation.isSuccess && (
              <div className="flex items-center gap-2 mt-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-emerald-400">API key saved successfully</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
