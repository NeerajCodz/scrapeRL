import React from 'react';
import {
  Activity,
  Zap,
  Brain,
  Target,
  Clock,
  TrendingUp,
  Database,
  Cpu,
  Globe,
  Play,
  RotateCcw,
} from 'lucide-react';
import { EpisodePanel } from './EpisodePanel';
import { AgentView } from './AgentView';
import { MemoryPanel } from './MemoryPanel';
import { ToolRegistry } from './ToolRegistry';
import { RewardChart } from './RewardChart';
import { ObservationView } from './ObservationView';
import { ActionPanel } from './ActionPanel';
import { useCurrentEpisode } from '@/hooks/useEpisode';

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: string | number;
  change?: string;
  color: 'emerald' | 'cyan' | 'purple' | 'amber';
}

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, label, value, change, color }) => {
  const colorClasses = {
    emerald: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-400',
    cyan: 'from-cyan-500/20 to-cyan-600/10 border-cyan-500/30 text-cyan-400',
    purple: 'from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-400',
    amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/30 text-amber-400',
  };

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} border rounded-xl p-4 backdrop-blur-sm`}>
      <div className="flex items-center justify-between">
        <div className={`p-2 rounded-lg bg-${color}-500/20`}>
          <Icon className={`w-5 h-5 ${colorClasses[color].split(' ').pop()}`} />
        </div>
        {change && (
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            {change}
          </span>
        )}
      </div>
      <div className="mt-3">
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-xs text-gray-400 mt-1">{label}</p>
      </div>
    </div>
  );
};

export const Dashboard: React.FC = () => {
  const { data: episode } = useCurrentEpisode();

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 rounded-lg">
              <Activity className="w-6 h-6 text-emerald-400" />
            </div>
            Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Monitor your RL scraping agents in real-time</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition-colors shadow-lg shadow-emerald-500/20">
            <Play className="w-4 h-4" />
            Start Episode
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors">
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Zap}
          label="Total Episodes"
          value={episode?.id ? '1' : '0'}
          color="emerald"
        />
        <StatCard
          icon={Target}
          label="Current Step"
          value={episode?.currentStep || 0}
          color="cyan"
        />
        <StatCard
          icon={TrendingUp}
          label="Total Reward"
          value={episode?.totalReward?.toFixed(2) || '0.00'}
          change="+12%"
          color="purple"
        />
        <StatCard
          icon={Clock}
          label="Avg Time/Step"
          value="1.2s"
          color="amber"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column - Episode & Agents */}
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
              <Brain className="w-4 h-4 text-emerald-400" />
              Episode Status
            </h3>
            <EpisodePanel />
          </div>
          
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
              <Cpu className="w-4 h-4 text-cyan-400" />
              Active Agents
            </h3>
            <AgentView />
          </div>
        </div>

        {/* Center Column - Observation & Charts */}
        <div className="lg:col-span-6 space-y-6">
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
              <Globe className="w-4 h-4 text-purple-400" />
              Current Observation
            </h3>
            <ObservationView />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Reward History
              </h3>
              <RewardChart />
            </div>
            
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
                <Zap className="w-4 h-4 text-amber-400" />
                Actions
              </h3>
              <ActionPanel />
            </div>
          </div>
        </div>

        {/* Right Column - Memory & Tools */}
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-pink-400" />
              Memory Layers
            </h3>
            <MemoryPanel />
          </div>
          
          <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
              <Cpu className="w-4 h-4 text-blue-400" />
              Tool Registry
            </h3>
            <ToolRegistry />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
