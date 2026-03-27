import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings as SettingsIcon,
  Key,
  Cpu,
  Wifi,
  Database,
  Image,
  RefreshCw,
  Save,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select, Toggle } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { apiClient } from '@/api/client';
import type { SystemSettings } from '@/types';

interface SettingsProps {
  className?: string;
}

export const Settings: React.FC<SettingsProps> = ({ className }) => {
  const queryClient = useQueryClient();
  const [localSettings, setLocalSettings] = useState<Partial<SystemSettings>>({});
  const [hasChanges, setHasChanges] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => apiClient.getSettings(),
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.healthCheck(),
    refetchInterval: 10000,
  });

  const updateMutation = useMutation({
    mutationFn: (newSettings: Partial<SystemSettings>) =>
      apiClient.updateSettings(newSettings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setHasChanges(false);
    },
  });

  useEffect(() => {
    if (settings) {
      setLocalSettings(settings);
    }
  }, [settings]);

  const handleChange = <K extends keyof SystemSettings>(
    key: K,
    value: SystemSettings[K]
  ) => {
    setLocalSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = () => {
    updateMutation.mutate(localSettings);
  };

  const handleReset = () => {
    if (settings) {
      setLocalSettings(settings);
      setHasChanges(false);
    }
  };

  const modelOptions = (settings?.availableModels ?? [
    'gpt-4-turbo',
    'gpt-4',
    'gpt-3.5-turbo',
    'claude-3-opus',
    'claude-3-sonnet',
  ]).map((m) => ({ value: m, label: m }));

  const logLevelOptions = [
    { value: 'debug', label: 'Debug' },
    { value: 'info', label: 'Info' },
    { value: 'warn', label: 'Warning' },
    { value: 'error', label: 'Error' },
  ];

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
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <SettingsIcon className="w-6 h-6 text-dark-500 animate-spin" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* API Configuration */}
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-dark-200 mb-3">
                <Key className="w-4 h-4" />
                API Configuration
              </div>
              <div className="space-y-3">
                <Input
                  label="API Key"
                  type="password"
                  placeholder="sk-..."
                  value={localSettings.apiKey ?? ''}
                  onChange={(e) => handleChange('apiKey', e.target.value)}
                  hint="Your OpenAI or provider API key"
                />
              </div>
            </div>

            {/* Model Settings */}
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-dark-200 mb-3">
                <Cpu className="w-4 h-4" />
                Model Settings
              </div>
              <div className="space-y-3">
                <Select
                  label="Default Model"
                  options={modelOptions}
                  value={localSettings.defaultModel ?? ''}
                  onChange={(e) => handleChange('defaultModel', e.target.value)}
                  placeholder="Select model"
                />
                <Input
                  label="Max Concurrent Agents"
                  type="number"
                  min={1}
                  max={10}
                  value={localSettings.maxConcurrentAgents ?? 4}
                  onChange={(e) =>
                    handleChange('maxConcurrentAgents', parseInt(e.target.value))
                  }
                />
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
                  onChange={(checked) => handleChange('enableWebSocket', checked)}
                />
                <Select
                  label="Log Level"
                  options={logLevelOptions}
                  value={localSettings.logLevel ?? 'info'}
                  onChange={(e) =>
                    handleChange('logLevel', e.target.value as SystemSettings['logLevel'])
                  }
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
                  onChange={(checked) =>
                    handleChange('memoryPersistence', checked)
                  }
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
                  onChange={(e) =>
                    handleChange('screenshotQuality', parseInt(e.target.value))
                  }
                  hint={`Quality: ${localSettings.screenshotQuality ?? 80}%`}
                />
              </div>
            </div>

            {/* Status Messages */}
            {updateMutation.isSuccess && (
              <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <span className="text-sm text-green-400">
                  Settings saved successfully
                </span>
              </div>
            )}

            {updateMutation.isError && (
              <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <AlertCircle className="w-4 h-4 text-red-400" />
                <span className="text-sm text-red-400">
                  {(updateMutation.error as Error).message}
                </span>
              </div>
            )}
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Button
          variant="ghost"
          onClick={handleReset}
          disabled={!hasChanges}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Reset
        </Button>
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!hasChanges}
          isLoading={updateMutation.isPending}
          leftIcon={<Save className="w-4 h-4" />}
        >
          Save Changes
        </Button>
      </CardFooter>
    </Card>
  );
};

export default Settings;
