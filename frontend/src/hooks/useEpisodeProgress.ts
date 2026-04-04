import { useEffect, useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { WebSocketMessage } from '@/types';

interface EpisodeProgressProps {
  episodeId: string | null;
  onProgressUpdate?: (data: WebSocketMessage) => void;
  onCompletion?: (data: WebSocketMessage) => void;
  onError?: (error: string) => void;
}

export function useEpisodeProgress({
  episodeId,
  onProgressUpdate,
  onCompletion,
  onError,
}: EpisodeProgressProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [totalReward, setTotalReward] = useState(0);
  const [progress, setProgress] = useState(0);
  const [lastAction, setLastAction] = useState<string>('');
  const [isCompleted, setIsCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { isConnected, lastMessage } = useWebSocket(
    episodeId ? `/ws/episode/${episodeId}` : '',
    {
      autoConnect: !!episodeId,
      onMessage: (message: WebSocketMessage) => {
        console.log('WebSocket message:', message);

        switch (message.type) {
          case 'connected':
            console.log('Connected to episode:', message.episode_id);
            break;

          case 'progress':
            if (message.step !== undefined) setCurrentStep(message.step);
            if (message.reward !== undefined) setTotalReward(prev => prev + message.reward!);
            if (message.progress !== undefined) setProgress(message.progress);
            if (message.action_type) setLastAction(message.action_type);
            onProgressUpdate?.(message);
            break;

          case 'completion':
            setIsCompleted(true);
            if (message.total_reward !== undefined) setTotalReward(message.total_reward);
            setProgress(100);
            onCompletion?.(message);
            break;

          case 'error':
            const errorMsg = message.error || 'Unknown error occurred';
            setError(errorMsg);
            onError?.(errorMsg);
            break;
        }
      },
    }
  );

  // Reset state when episode changes
  useEffect(() => {
    if (episodeId) {
      setCurrentStep(0);
      setTotalReward(0);
      setProgress(0);
      setLastAction('');
      setIsCompleted(false);
      setError(null);
    }
  }, [episodeId]);

  return {
    isConnected,
    currentStep,
    totalReward,
    progress,
    lastAction,
    isCompleted,
    error,
    lastMessage,
  };
}

export default useEpisodeProgress;
