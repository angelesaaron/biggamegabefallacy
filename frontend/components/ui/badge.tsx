import * as React from 'react';
import { cn } from '@/lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'danger' | 'muted';
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  const variants: Record<string, string> = {
    default: 'bg-sr-primary/10 text-sr-primary border-sr-primary/30',
    success: 'bg-sr-success/10 text-sr-success border-sr-success/30',
    danger: 'bg-sr-danger/10 text-sr-danger border-sr-danger/30',
    muted: 'bg-sr-surface text-sr-text-muted border-sr-border',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-badge border px-2 py-0.5 text-xs font-medium',
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
