import React from 'react';
import { classNames } from '@/utils/helpers';

type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';
type BadgeSize = 'sm' | 'md' | 'lg';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  pulse?: boolean;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  pulse = false,
  icon,
  className,
  ...props
}) => {
  const variantStyles: Record<BadgeVariant, string> = {
    success: 'bg-green-500/20 text-green-400 border-green-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
    info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    neutral: 'bg-dark-600/50 text-dark-300 border-dark-500/30',
  };

  const dotColors: Record<BadgeVariant, string> = {
    success: 'bg-green-400',
    warning: 'bg-yellow-400',
    error: 'bg-red-400',
    info: 'bg-blue-400',
    neutral: 'bg-dark-400',
  };

  const sizeStyles: Record<BadgeSize, string> = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-0.5 text-xs',
    lg: 'px-3 py-1 text-sm',
  };

  return (
    <span
      className={classNames(
        'inline-flex items-center gap-1.5 rounded-full font-medium border',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={classNames(
            'w-1.5 h-1.5 rounded-full',
            dotColors[variant],
            pulse && 'animate-pulse'
          )}
        />
      )}
      {icon}
      {children}
    </span>
  );
};

interface StatusBadgeProps {
  status: string;
  size?: BadgeSize;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
}) => {
  const getVariant = (): BadgeVariant => {
    switch (status.toLowerCase()) {
      case 'running':
      case 'active':
      case 'acting':
      case 'completed':
      case 'success':
        return 'success';
      case 'thinking':
      case 'processing':
        return 'info';
      case 'idle':
      case 'waiting':
      case 'pending':
      case 'timeout':
        return 'warning';
      case 'error':
      case 'failed':
        return 'error';
      default:
        return 'neutral';
    }
  };

  const shouldPulse = ['running', 'acting', 'thinking', 'processing'].includes(
    status.toLowerCase()
  );

  return (
    <Badge variant={getVariant()} size={size} dot pulse={shouldPulse}>
      {status}
    </Badge>
  );
};

export default Badge;
