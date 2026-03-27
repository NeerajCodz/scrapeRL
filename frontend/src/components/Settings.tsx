import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings as SettingsIcon,
  Key,
  Wifi,
  Database,
  Image,
  AlertCircle,
  CheckCircle,
  Eye,
  EyeOff,
  Zap,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
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
    <Card className={className}>
      <CardHeader
        title="Settings"
        icon={<SettingsIcon className="w-4 h-4" />}
        action={
          health && (
            <Badge variant={health.status === 'ok' ? 'success' : 'error'} dot>
              {health.status === 'ok' ? 'Connected' : 'Disconnected'}
            </Badge>
          )
        }
      />
      <CardContent>
        {settingsLoading ? (
          <div className="flex items-center justify-center py-8">
            <SettingsIcon className="w-6 h-6 text-dark-500 animate-spin" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* API Key Required Warning */}
            {keyRequired?.required && (
              <div className="flex items-center gap-2 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <AlertCircle className="w-4 h-4 text-yellow-400" />
                <span className="text-sm text-yellow-400">
                  {keyRequired.message}
                </span>
              </div>
            )}

            {/* Model Selection */}
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-dark-200 mb-3">
                <Zap className="w-4 h-4" />
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
                <p className="text-xs text-dark-400 mt-1">Switching model...</p>
              )}
            </div>

            {/* API Keys Section */}
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-dark-200 mb-3">
                <Key className="w-4 h-4" />
                API Keys
              </div>
              <p className="text-xs text-dark-400 mb-4">
                Enter your API keys to use the corresponding models. Keys are stored in your browser session.
              </p>
              <div className="space-y-4">
                {providers.map((provider) => {
                  const isConfigured = settingsData?.api_keys_configured?.[provider.id] ?? false;
                  return (
                    <div key={provider.id} className="p-3 bg-dark-800/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-lg">{provider.icon}</span>
                          <div>
                            <span className="text-sm font-medium text-dark-100">
                              {provider.name}
                            </span>
                            <p className="text-xs text-dark-400">{provider.description}</p>
                          </div>
                        </div>
                        <Badge variant={isConfigured ? 'success' : 'warning'} size="sm">
                          {isConfigured ? 'Configured' : 'Not Set'}
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
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-200"
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
            </div>

            {/* Connection Settings */}
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-dark-200 mb-3">
                <Wifi className="w-4 h-4" />
                Connection
              </div>
              <div className="space-y-3">
                <Toggle
                  label="WebSocket Updates"
                  description="Enable real-time episode updates"
                  checked={localSettings.enableWebSocket ?? true}
                  onChange={(checked) => {
                    setLocalSettings((prev) => ({ ...prev, enableWebSocket: checked }));
                  }}
                />
              </div>
            </div>

            {/* Storage Settings */}
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-dark-200 mb-3">
                <Database className="w-4 h-4" />
                Storage
              </div>
              <div className="space-y-3">
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

            {/* Screenshot Settings */}
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-dark-200 mb-3">
                <Image className="w-4 h-4" />
                Screenshots
              </div>
              <div className="space-y-3">
                <Input
                  label="Screenshot Quality"
                  type="range"
                  min={10}
                  max={100}
                  value={localSettings.screenshotQuality ?? 80}
                  onChange={(e) => {
                    setLocalSettings((prev) => ({
                      ...prev,
                      screenshotQuality: parseInt(e.target.value),
                    }));
                  }}
                  hint={`Quality: ${localSettings.screenshotQuality ?? 80}%`}
                />
              </div>
            </div>

            {/* Status Messages */}
            {updateApiKeyMutation.isSuccess && (
              <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <span className="text-sm text-green-400">API key saved successfully</span>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default Settings;
