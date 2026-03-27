import React, { useState } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Square,
  Clock,
  Target,
  Zap,
  TrendingUp,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import {
  useCurrentEpisode,
  useResetEpisode,
  useTerminateEpisode,
} from '@/hooks/useEpisode';
import { formatDuration, formatTimestamp, calculateProgress } from '@/utils/helpers';

interface EpisodePanelProps {
  className?: string;
}

export const EpisodePanel: React.FC<EpisodePanelProps> = ({ className }) => {
  const { data: episode, isLoading } = useCurrentEpisode();
  const resetMutation = useResetEpisode();
  const terminateMutation = useTerminateEpisode();
  const [isRunning, setIsRunning] = useState(false);

  const handleReset = () => {
    resetMutation.mutate({
      task: {
        description: 'Default scraping task',
        targetUrl: 'https://example.com',
        objectives: ['Extract main content'],
      },
    });
  };

  const handleToggleRun = () => {
    setIsRunning(!isRunning);
  };

  const handleTerminate = () => {
    if (episode?.id) {
      terminateMutation.mutate(episode.id);
    }
  };

  const progress = episode
    ? calculateProgress(episode.currentStep, episode.config.maxSteps)
    : 0;

  const elapsedTime = episode
    ? Date.now() - new Date(episode.startTime).getTime()
    : 0;

  return (
    <Card className={className}>
      <CardHeader
        title="Episode Control"
        icon={<Zap className="w-4 h-4" />}
        action={
          episode && (
            <StatusBadge status={episode.status} />
          )
        }
      />
      <CardContent>
        {/* Control Buttons */}
        <div className="flex gap-2 mb-4">
          <Button
            variant="primary"
            size="sm"
            onClick={handleReset}
            isLoading={resetMutation.isPending}
            leftIcon={<RotateCcw className="w-4 h-4" />}
          >
            Reset
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleToggleRun}
            disabled={!episode}
            leftIcon={
              isRunning ? (
                <Pause className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )
            }
          >
            {isRunning ? 'Pause' : 'Run'}
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={handleTerminate}
            disabled={!episode || episode.status !== 'running'}
            isLoading={terminateMutation.isPending}
            leftIcon={<Square className="w-4 h-4" />}
          >
            Stop
          </Button>
        </div>

        {/* Progress Bar */}
        <div className="mb-4">
          <div className="flex justify-between text-sm text-dark-400 mb-1">
            <span>Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-accent-primary to-accent-tertiary rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-dark-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
              <Target className="w-3 h-3" />
              <span>Step</span>
            </div>
            <div className="text-xl font-semibold text-dark-100">
              {isLoading ? '-' : `${episode?.currentStep ?? 0}`}
              <span className="text-sm text-dark-500 font-normal">
                /{episode?.config.maxSteps ?? 100}
              </span>
            </div>
          </div>

          <div className="bg-dark-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
              <Clock className="w-3 h-3" />
              <span>Time</span>
            </div>
            <div className="text-xl font-semibold text-dark-100">
              {episode ? formatDuration(elapsedTime) : '--:--'}
            </div>
          </div>

          <div className="bg-dark-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
              <TrendingUp className="w-3 h-3" />
              <span>Total Reward</span>
            </div>
            <div className="text-xl font-semibold">
              <span
                className={
                  (episode?.totalReward ?? 0) >= 0
                    ? 'text-green-400'
                    : 'text-red-400'
                }
              >
                {episode?.totalReward?.toFixed(2) ?? '0.00'}
              </span>
            </div>
          </div>

          <div className="bg-dark-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
              <Zap className="w-3 h-3" />
              <span>Budget</span>
            </div>
            <div className="text-xl font-semibold text-dark-100">
              ${episode?.config.budget?.toFixed(2) ?? '0.00'}
            </div>
          </div>
        </div>

        {/* Task Info */}
        {episode?.task && (
          <div className="mt-4 p-3 bg-dark-900/50 rounded-lg">
            <div className="text-xs text-dark-400 mb-1">Current Task</div>
            <div className="text-sm text-dark-200 mb-2">
              {episode.task.description}
            </div>
            <div className="flex flex-wrap gap-1">
              {episode.task.objectives.slice(0, 3).map((obj, i) => (
                <Badge key={i} variant="info" size="sm">
                  {obj}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Timeline */}
        {episode && (
          <div className="mt-4">
            <div className="text-xs text-dark-400 mb-2">Timeline</div>
            <div className="space-y-2 max-h-32 overflow-y-auto">
              <div className="timeline-item">
                <div className="timeline-dot" />
                <div className="text-xs text-dark-300">
                  <span className="text-dark-500">
                    {formatTimestamp(episode.startTime)}
                  </span>
                  {' · '}Episode started
                </div>
              </div>
              {episode.actions.slice(-3).map((action, i) => (
                <div key={i} className="timeline-item">
                  <div className="timeline-dot" style={{ backgroundColor: '#6366f1' }} />
                  <div className="text-xs text-dark-300">
                    <span className="text-dark-500">
                      {formatTimestamp(action.timestamp)}
                    </span>
                    {' · '}
                    {action.type}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default EpisodePanel;
