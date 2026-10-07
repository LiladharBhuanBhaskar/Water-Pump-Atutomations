import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  hover?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  subtitle,
  action,
  icon,
  className = '',
  hover = false,
}) => {
  return (
    <div
      className={`glass-panel rounded-2xl p-5 ${
        hover ? 'glass-panel-hover' : ''
      } ${className}`}
    >
      {(title || action || icon) && (
        <div className="flex items-center justify-between gap-4 mb-4 pb-3 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            {icon && (
              <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                {icon}
              </div>
            )}
            <div>
              {title && <h3 className="font-bold text-white text-base tracking-tight">{title}</h3>}
              {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
            </div>
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
};
