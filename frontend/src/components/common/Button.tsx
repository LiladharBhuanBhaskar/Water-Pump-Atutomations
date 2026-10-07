import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'warning' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  icon,
  className = '',
  ...props
}) => {
  const variantStyles = {
    primary:
      'bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-600/20 border border-cyan-400/30 active:scale-[0.98]',
    secondary:
      'bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 active:scale-[0.98]',
    danger:
      'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/25 border border-rose-400/40 active:scale-[0.98]',
    warning:
      'bg-amber-600 hover:bg-amber-500 text-white shadow-lg shadow-amber-600/25 border border-amber-400/40 active:scale-[0.98]',
    outline:
      'bg-transparent hover:bg-slate-800/60 text-slate-300 border border-slate-700 hover:text-white',
    ghost:
      'bg-transparent hover:bg-slate-800/40 text-slate-400 hover:text-slate-200 border border-transparent',
  };

  const sizeStyles = {
    sm: 'text-xs px-3 py-1.5 rounded-lg gap-1.5 font-medium',
    md: 'text-sm px-4 py-2 rounded-xl gap-2 font-semibold',
    lg: 'text-base px-6 py-3 rounded-2xl gap-2.5 font-bold',
  };

  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : icon}
      {children}
    </button>
  );
};
