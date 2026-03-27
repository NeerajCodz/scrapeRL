import React from 'react';
import { classNames } from '@/utils/helpers';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'bordered' | 'elevated' | 'glass';
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  padding = 'md',
  className,
  ...props
}) => {
  const variantStyles = {
    default: 'bg-dark-800 border border-dark-700',
    bordered: 'bg-transparent border-2 border-dark-600',
    elevated: 'bg-dark-800 shadow-xl shadow-black/20',
    glass: 'bg-dark-800/80 backdrop-blur-sm border border-dark-700/50',
  };

  const paddingStyles = {
    none: 'p-0',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
  };

  return (
    <div
      className={classNames(
        'rounded-xl',
        variantStyles[variant],
        paddingStyles[padding],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  action,
  icon,
  className,
  ...props
}) => {
  return (
    <div
      className={classNames(
        'flex items-center justify-between mb-4 pb-3 border-b border-dark-700',
        className
      )}
      {...props}
    >
      <div className="flex items-center gap-3">
        {icon && (
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-dark-700 text-dark-300">
            {icon}
          </div>
        )}
        <div>
          <h3 className="text-lg font-semibold text-dark-100">{title}</h3>
          {subtitle && (
            <p className="text-sm text-dark-400 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
};

type CardContentProps = React.HTMLAttributes<HTMLDivElement>;

export const CardContent: React.FC<CardContentProps> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div className={classNames('', className)} {...props}>
      {children}
    </div>
  );
};

type CardFooterProps = React.HTMLAttributes<HTMLDivElement>;

export const CardFooter: React.FC<CardFooterProps> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div
      className={classNames(
        'flex items-center justify-end gap-3 mt-4 pt-3 border-t border-dark-700',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export default Card;
