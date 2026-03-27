import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  Cell,
  PieChart,
  Pie,
} from 'recharts';
import { TrendingUp, Award, Target, Zap } from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useEpisodeRewards, useCurrentEpisode } from '@/hooks/useEpisode';
import { formatReward } from '@/utils/helpers';

interface RewardChartProps {
  className?: string;
}

const COLORS = [
  '#10a37f',
  '#6366f1',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
];

const CustomTooltip: React.FC<{
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string;
}> = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="bg-dark-800 border border-dark-600 rounded-lg p-3 shadow-xl">
      <div className="text-xs text-dark-400 mb-2">Step {label}</div>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-dark-300">{entry.name}:</span>
          <span
            className={entry.value >= 0 ? 'text-green-400' : 'text-red-400'}
          >
            {formatReward(entry.value)}
          </span>
        </div>
      ))}
    </div>
  );
};

export const RewardChart: React.FC<RewardChartProps> = ({ className }) => {
  const { data: episode } = useCurrentEpisode();
  const { data: rewards, isLoading } = useEpisodeRewards(episode?.id);

  const chartData = React.useMemo(() => {
    if (!rewards || rewards.length === 0) return [];
    return rewards.map((r, i) => ({
      step: i + 1,
      total: r.total,
      cumulative: r.cumulative,
      ...r.components.reduce(
        (acc, c) => ({ ...acc, [c.name]: c.value }),
        {} as Record<string, number>
      ),
    }));
  }, [rewards]);

  const componentNames = React.useMemo(() => {
    if (!rewards || rewards.length === 0) return [];
    const names = new Set<string>();
    rewards.forEach((r) => r.components.forEach((c) => names.add(c.name)));
    return Array.from(names);
  }, [rewards]);

  const latestReward = rewards?.[rewards.length - 1];
  const componentBreakdown = latestReward?.components ?? [];

  const pieData = componentBreakdown.map((c, i) => ({
    name: c.name,
    value: Math.abs(c.value),
    fill: COLORS[i % COLORS.length],
    originalValue: c.value,
  }));

  const stats = React.useMemo(() => {
    if (!rewards || rewards.length === 0) {
      return { total: 0, avg: 0, max: 0, min: 0 };
    }
    const totals = rewards.map((r) => r.total);
    return {
      total: rewards[rewards.length - 1]?.cumulative ?? 0,
      avg: totals.reduce((a, b) => a + b, 0) / totals.length,
      max: Math.max(...totals),
      min: Math.min(...totals),
    };
  }, [rewards]);

  return (
    <Card className={className}>
      <CardHeader
        title="Rewards"
        icon={<Award className="w-4 h-4" />}
        action={
          latestReward && (
            <Badge
              variant={latestReward.total >= 0 ? 'success' : 'error'}
              size="sm"
            >
              {formatReward(latestReward.total)}
            </Badge>
          )
        }
      />
      <CardContent>
        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-2 mb-4">
          <div className="bg-dark-900/50 rounded-lg p-2 text-center">
            <div className="flex items-center justify-center gap-1 text-xs text-dark-400 mb-1">
              <TrendingUp className="w-3 h-3" />
              <span>Total</span>
            </div>
            <div
              className={`text-lg font-semibold ${
                stats.total >= 0 ? 'text-green-400' : 'text-red-400'
              }`}
            >
              {formatReward(stats.total)}
            </div>
          </div>
          <div className="bg-dark-900/50 rounded-lg p-2 text-center">
            <div className="flex items-center justify-center gap-1 text-xs text-dark-400 mb-1">
              <Target className="w-3 h-3" />
              <span>Avg</span>
            </div>
            <div className="text-lg font-semibold text-dark-200">
              {formatReward(stats.avg)}
            </div>
          </div>
          <div className="bg-dark-900/50 rounded-lg p-2 text-center">
            <div className="flex items-center justify-center gap-1 text-xs text-dark-400 mb-1">
              <Zap className="w-3 h-3" />
              <span>Max</span>
            </div>
            <div className="text-lg font-semibold text-green-400">
              {formatReward(stats.max)}
            </div>
          </div>
          <div className="bg-dark-900/50 rounded-lg p-2 text-center">
            <div className="flex items-center justify-center gap-1 text-xs text-dark-400 mb-1">
              <Zap className="w-3 h-3" />
              <span>Min</span>
            </div>
            <div className="text-lg font-semibold text-red-400">
              {formatReward(stats.min)}
            </div>
          </div>
        </div>

        {/* Cumulative Reward Chart */}
        {isLoading ? (
          <div className="h-40 flex items-center justify-center">
            <Award className="w-6 h-6 text-dark-500 animate-pulse" />
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-40 flex items-center justify-center text-dark-500">
            <div className="text-center">
              <Award className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No reward data</p>
            </div>
          </div>
        ) : (
          <>
            <div className="h-40 mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="rewardGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10a37f" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10a37f" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#40414f" />
                  <XAxis
                    dataKey="step"
                    stroke="#8e8ea0"
                    fontSize={10}
                    tickLine={false}
                  />
                  <YAxis stroke="#8e8ea0" fontSize={10} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="cumulative"
                    name="Cumulative"
                    stroke="#10a37f"
                    fill="url(#rewardGradient)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Component Breakdown Bar Chart */}
            {componentNames.length > 0 && (
              <div className="h-32 mb-4">
                <div className="text-xs text-dark-400 mb-2">
                  Reward Components
                </div>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData.slice(-10)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#40414f" />
                    <XAxis
                      dataKey="step"
                      stroke="#8e8ea0"
                      fontSize={10}
                      tickLine={false}
                    />
                    <YAxis stroke="#8e8ea0" fontSize={10} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    {componentNames.map((name, i) => (
                      <Bar
                        key={name}
                        dataKey={name}
                        stackId="a"
                        fill={COLORS[i % COLORS.length]}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Pie Chart for Latest Breakdown */}
            {pieData.length > 0 && (
              <div className="flex items-center gap-4">
                <div className="w-24 h-24">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={20}
                        outerRadius={35}
                        paddingAngle={2}
                      >
                        {pieData.map((entry, i) => (
                          <Cell key={i} fill={entry.fill} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex-1 grid grid-cols-2 gap-1">
                  {componentBreakdown.map((c, i) => (
                    <div key={c.name} className="flex items-center gap-2 text-xs">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: COLORS[i % COLORS.length] }}
                      />
                      <span className="text-dark-400 truncate">{c.name}</span>
                      <span
                        className={
                          c.value >= 0 ? 'text-green-400' : 'text-red-400'
                        }
                      >
                        {formatReward(c.value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default RewardChart;
