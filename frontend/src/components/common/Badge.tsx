import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'neutral';
  size?: 'sm' | 'md';
  dot?: boolean;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  className = '',
}) => {
  const variantStyles = {
    default: 'bg-slate-800/80 text-slate-300 border-slate-700/60',
    success: 'bg-emerald-950/80 text-emerald-400 border-emerald-800/50',
    warning: 'bg-amber-950/80 text-amber-400 border-amber-800/50',
    danger: 'bg-rose-950/80 text-rose-400 border-rose-800/50',
    info: 'bg-cyan-950/80 text-cyan-400 border-cyan-800/50',
    purple: 'bg-purple-950/80 text-purple-400 border-purple-800/50',
    neutral: 'bg-slate-900 text-slate-400 border-slate-800',
  };

  const dotStyles = {
    default: 'bg-slate-400',
    success: 'bg-emerald-400 animate-pulse',
    warning: 'bg-amber-400',
    danger: 'bg-rose-400 animate-ping',
    info: 'bg-cyan-400',
    purple: 'bg-purple-400',
    neutral: 'bg-slate-500',
  };

  const sizeStyles = {
    sm: 'text-[10px] px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
  };

  return (
    <span
      className={`inline-flex items-center font-semibold rounded-full border ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotStyles[variant]}`} />}
      {children}
    </span>
  );
};
